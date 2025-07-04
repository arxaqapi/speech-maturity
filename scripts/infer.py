import sys

import librosa
import numpy as np
import pandas as pd
import speechbrain as sb
import torch
from hyperpyyaml import load_hyperpyyaml
from speechbrain.lobes.models.fairseq_wav2vec import FairseqWav2Vec2


class EmoIdBrain(sb.Brain):
    def compute_forward(self, batch, stage):
        """Computation pipeline based on a encoder + emotion classifier."""

        batch = batch.to(self.device)
        wavs_chi, lens_chi = batch.sig_chi

        outputs_chi = self.modules.wav2vec2(wavs_chi)
        # last dim will be used for AdaptativeAVG pool

        asr_features = self.get_asr_features(wavs_chi)
        outputs_chi = self.get_wa_outputs(
            outputs_chi,
            self.modules.weighted_average_chi,
            mean_pool_first=self.hparams.mean_pool_first_chi,
            lens=lens_chi,
        )
        if self.hparams.combine_asr == "concat":
            outputs_chi = torch.cat((outputs_chi, asr_features), dim=1)
        else:
            outputs_chi = (
                1 - self.hparams.combine_factor_asr
            ) * outputs_chi + self.hparams.combine_factor_asr * asr_features

        outputs_chi = self.modules.output_mlp_chi(self.modules.dnn_chi(outputs_chi))

        return outputs_chi

    def get_asr_features(self, wavs, apply_avg=True):
        with torch.no_grad():
            embeddings = self.hparams.wav2vec_asr(wavs)
            if apply_avg:
                embeddings = self.hparams.avg_pool(embeddings).squeeze_()
        return embeddings

    def get_wa_outputs(self, outputs, wa, mean_pool_first=True, lens=None):
        if mean_pool_first:
            avg_outputs = []
            for i in range(len(outputs)):
                avg_output = self.hparams.avg_pool(outputs[i], lens)
                avg_output = avg_output.view(avg_output.shape[0], -1)
                avg_outputs.append(avg_output)
            outputs = torch.stack(avg_outputs).permute(1, 2, 0)
            outputs = wa(outputs)
        else:  # WA first
            outputs = outputs.permute(1, 2, 3, 0)
            outputs = wa(outputs)  # B,T,D
            outputs = self.hparams.avg_pool(outputs, lens)
            outputs = outputs.view(outputs.shape[0], -1)

        return outputs

    def compute_objectives(self, outputs_chi, batch, stage):
        """Computes the loss using speaker-id as label."""
        chi_true = batch.chi_true

        """to meet the input form of nll loss"""
        predictions_chi = self.hparams.log_softmax(outputs_chi)

        loss = self.hparams.compute_cost(predictions_chi, chi_true)

        if stage != sb.Stage.TRAIN:
            self.error_metrics.append(batch.id, predictions_chi, chi_true)
        return loss

    def fit_batch(self, batch):
        """Trains the parameters given a single batch in input"""
        predictions_chi = self.compute_forward(batch, sb.Stage.TRAIN)
        loss = self.compute_objectives(predictions_chi, batch, sb.Stage.TRAIN)

        loss.backward()
        if self.check_gradients(loss):
            self.wav2vec2_optimizer.step()
            self.optimizer.step()

        self.wav2vec2_optimizer.zero_grad()
        self.optimizer.zero_grad()

        return loss.detach()

    def evaluate_batch(self, batch, stage):
        predictions_chi = self.compute_forward(batch, stage)
        loss = self.compute_objectives(predictions_chi, batch, stage)

        # Convert predictions (logits) to probabilities using softmax
        probabilities = torch.nn.functional.softmax(predictions_chi, dim=-1)

        # Get predicted class labels (argmax)
        predicted_labels = torch.argmax(probabilities, dim=-1)

        # Store predictions
        batch_ids = batch.id  # Get batch sample IDs
        true_labels = batch.chi_true  # Get true labels
        # NOTE - index to label name
        inv_dict_map = {
            1: "Non-Canonical",
            2: "Canonical",
            3: "Laughing",
            4: "Crying",
            0: "Junk",
        }
        # Store as a dictionary for easy access later
        for i, sample_id in enumerate(batch_ids):
            pred_lab = predicted_labels[i].item()
            self.predictions_list.append(
                {
                    "id": sample_id,
                    "predicted_label": pred_lab,
                    "prediction_class_name": inv_dict_map[pred_lab],
                    "logits": predictions_chi[i].tolist(),
                    "probabilities": probabilities[i].tolist(),
                }
            )

        return loss.detach().cpu()

    def on_stage_start(self, stage, epoch=None):
        """Gets called at the beginning of each epoch.
        Arguments
        ---------
        stage : sb.Stage
            One of sb.Stage.TRAIN, sb.Stage.VALID, or sb.Stage.TEST.
        epoch : int
            The currently-starting epoch. This is passed
            `None` during the test stage.
        """
        # Set up statistics trackers for this stage
        self.loss_metric = sb.utils.metric_stats.MetricStats(
            metric=sb.nnet.losses.nll_loss
        )

        # Set up evaluation-only statistics trackers
        if stage != sb.Stage.TRAIN:
            self.error_metrics = self.hparams.error_stats()
            self.predictions_list = []

    def on_stage_end(self, stage, stage_loss, epoch=None):
        """Gets called at the end of an epoch.
        Arguments
        ---------
        stage : sb.Stage
            One of sb.Stage.TRAIN, sb.Stage.VALID, sb.Stage.TEST
        stage_loss : float
            The average loss for all of the data processed in this stage.
        epoch : int
            The currently-starting epoch. This is passed
            `None` during the test stage.
        """

        # Store the train loss until the validation stage.
        if stage == sb.Stage.TRAIN:
            self.train_loss = stage_loss

        # Summarize the statistics from the stage for record-keeping.
        else:
            stats = {
                "loss": stage_loss,
                "error_rate_f1": 1 - self.error_metrics.summarize("macro_f1"),
                "error_rate_UAR": 1 - self.error_metrics.summarize("UAR"),
                "error_rate_f1_UAR": 1
                - (
                    0.5 * self.error_metrics.summarize("macro_f1")
                    + 0.5 * self.error_metrics.summarize("UAR")
                ),
            }

        # At the end of validation...
        if stage == sb.Stage.VALID:
            old_lr, new_lr = self.hparams.lr_annealing(stats["error_rate_UAR"])
            sb.nnet.schedulers.update_learning_rate(self.optimizer, new_lr)

            (
                old_lr_wav2vec2,
                new_lr_wav2vec2,
            ) = self.hparams.lr_annealing_wav2vec2(stats["error_rate_UAR"])
            sb.nnet.schedulers.update_learning_rate(
                self.wav2vec2_optimizer, new_lr_wav2vec2
            )

            # The train_logger writes a summary to stdout and to the logfile.
            self.hparams.train_logger.log_stats(
                {"Epoch": epoch, "lr": old_lr, "wave2vec_lr": old_lr_wav2vec2},
                train_stats={"loss": self.train_loss},
                valid_stats=stats,
            )

            # Save the current checkpoint and delete previous checkpoints,
            self.checkpointer.save_and_keep_only(
                meta=stats, min_keys=["error_rate_UAR"]
            )

            with open(self.hparams.train_log, "a") as w:
                self.error_metrics.write_stats(w)
        # We also write statistics about test data to stdout and to logfile.
        if stage == sb.Stage.TEST:
            self.hparams.train_logger.log_stats(
                {"Epoch loaded": self.hparams.epoch_counter.current},
                test_stats=stats,
            )
            with open(self.hparams.train_log, "a") as w:
                self.error_metrics.write_stats(w)

            # Print predictions or save to file
            predictions_df = pd.DataFrame(self.predictions_list)
            # CHANGE
            predictions_df.to_csv(
                f"{self.hparams.output_folder}/predictions.csv", index=False
            )

            print(predictions_df.head())

    def init_optimizers(self):
        "Initializes the wav2vec2 optimizer and model optimizer"
        self.wav2vec2_optimizer = self.hparams.wav2vec2_opt_class(
            self.modules.wav2vec2.parameters()
        )
        self.optimizer = self.hparams.opt_class(self.hparams.model.parameters())

        if self.checkpointer is not None:
            self.checkpointer.add_recoverable("wav2vec2_opt", self.wav2vec2_optimizer)
            self.checkpointer.add_recoverable("optimizer", self.optimizer)


def dataio_prep(hparams):
    """This function prepares the datasets to be used in the brain class.
    It also defines the data processing pipeline through user-defined
    functions. We expect `prepare_mini_librispeech` to have been called before
    this, so that the `train.json`, `valid.json`,  and `valid.json` manifest
    files are available.
    Arguments
    ---------
    hparams : dict
        This dictionary is loaded from the `train.yaml` file, and it includes
        all the hyperparameters needed for dataset construction and loading.
    Returns
    -------
    datasets : dict
        Contains two keys, "train" and "valid" that correspond
        to the appropriate DynamicItemDataset object.
    """

    # Define audio pipeline
    @sb.utils.data_pipeline.takes("wav")
    @sb.utils.data_pipeline.provides("sig_chi")
    def audio_pipeline_chi(wav):
        """Load the signal, and pass it and its length to the corruption class.
        This is done on the CPU in the `collate_fn`."""
        data, rate = librosa.load(
            wav, sr=16000, mono=True
        )  # downsample all the audio to 16kHz
        if len(data) / rate < 0.07:
            pad_zeros_num = int(0.07 * rate) - len(data)
            pad_zeros = np.zeros(pad_zeros_num)
            data = np.r_[data, pad_zeros]
        data = torch.from_numpy(data).float()
        return data

    @sb.utils.data_pipeline.takes("label")
    @sb.utils.data_pipeline.provides("chi_true")
    def label_pipeline_chi(input):
        dict_map = {
            "Non-Canonical": 1,
            "Canonical": 2,
            "Laughing": 3,
            "Crying": 4,
            "Junk": 0,
        }
        if input in dict_map:
            yield dict_map[input]
        yield 0

    # Define datasets. We also connect the dataset with the data processing
    # functions defined above.
    datasets = {}
    for dataset in ["train", "valid", "test"]:
        datasets[dataset] = sb.dataio.dataset.DynamicItemDataset.from_json(
            json_path=hparams[f"{dataset}_annotation"],
            replacements={"data_root": hparams["data_folder"]},
            dynamic_items=[audio_pipeline_chi, label_pipeline_chi],
            output_keys=["id", "sig_chi", "chi_true"],
        )

    return datasets


if __name__ == "__main__":
    # Reading command line arguments.
    hparams_file, run_opts, overrides = sb.parse_arguments(sys.argv[1:])
    # CHANGE if you are using GPU
    run_opts["device"] = "cpu"  # cpu, gpu, mps

    # Load hyperparameters file with command-line overrides.
    with open(hparams_file) as fin:
        hparams = load_hyperpyyaml(fin, overrides)

    # Create experiment directory
    sb.create_experiment_directory(
        experiment_directory=hparams["output_folder"],
        hyperparams_to_save=hparams_file,
        overrides=overrides,
    )

    # Create dataset objects "train", "valid", and "test".
    datasets = dataio_prep(hparams)

    # hparams["wav2vec2"] = hparams["wav2vec2"].to(run_opts["device"])

    # Initialize the Brain object to prepare for mask training.
    emo_id_brain = EmoIdBrain(
        modules=hparams["modules"],
        opt_class=hparams["opt_class"],
        hparams=hparams,
        run_opts=run_opts,
        checkpointer=hparams["checkpointer"],
    )
    emo_id_brain.checkpointer.recover_if_possible()
    emo_id_brain.modules.eval()

    # Load the best checkpoint for evaluation
    test_stats = emo_id_brain.evaluate(
        test_set=datasets["test"],
        min_key="error_rate_UAR",
        test_loader_kwargs=hparams["test_dataloader_options"],
    )
