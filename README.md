# Speech Maturity Classifier

## Requirements
This project relies on [uv](https://github.com/astral-sh/uv) to run and handle dependencies correctly, ensure you have it installed.

You would also need [git-lfs](https://git-lfs.com/) installed so that the submodules large files are correctly downloaded.

## Installation Steps
Clone the repo:
```bash
$ git clone --recurse-submodules https://github.com/arxaqapi/speech-maturity
```

Install all locked dependencies:
```bash
$ uv sync
```


## Usage

### Inference
The recommended way of using the vocal maturity classifier for inference is to use the `run.sh` script that handles most of the heavy lifting.
```sh
$ sh run.sh
```

You could also have a more fine-grained control on how to run it by directly invoking the `infer.py` script, make sure that the hyper-parameters are correctly set in the `hparams.yaml` file.
```sh
$ uv run scripts/infer.py hparams/hparams.yaml
```

### Audio preparation
The `run.sh` script awaits the audio files to be in the folder defined by the `audios_path` variable, by default set to `audio`.
To prepare the json input file, `run.sh` automatically runs `scripts/gen_json.py`.


## Paper/BibTex Citation
```bibtex
@article{zhang2025employing,
    title={Employing self-supervised learning models for cross-linguistic child speech maturity classification},
    author={Zhang, Theo and Suresh, Madurya and Warlaumont, Anne and Hitczenko, Kasia and Cristia, Alejandrina and Cychosz, Margaret},
    booktitle={Interspeech},
    year={2025}
}
```

## Acknowledgement
- https://github.com/jialuli3/speechbrain/tree/ef9038cd076dd2789755f48c0f95955c8570be5a/recipes/BabbleCor
- https://github.com/spoglab-stanford/w2v2-pro-sm/tree/main/speechbrain/recipes/W2V2-LL4300-Pro-SM

