# module purge
# module load uv
# module load audio-tools

audios_path=audio
output_folder=debug_out

# NOTE - Prepare output folder
mkdir -p $output_folder/myst_checkpoints
target_path=$(realpath w2v2-pro-sm)
link_path="$(realpath)/$output_folder/myst_checkpoints"
# ln -s "$(realpath w2v2-pro-sm)/*." "$(realpath)/$output_folder/myst_checkpoints"
find $target_path -maxdepth 1 -mindepth 1 -exec ln -vs - "{}" "$link_path" \;

# # NOTE - prepare wav files
uv run scripts/gen_json.py \
    --audio $audios_path \
    --output $output_folder/audio_chunks.json

# NOTE - evaluate
uv run scripts/infer.py hparams/hparams.yaml \
    --output_folder=$output_folder \
    --train_annotation="$output_folder/audio_chunks.json" \
    --valid_annotation="$output_folder/audio_chunks.json" \
    --test_annotation="$output_folder/audio_chunks.json" 
    #  \ --device="cuda"
