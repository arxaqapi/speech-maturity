import argparse
import json
from pathlib import Path
from typing import Generator


def log(s: str) -> None:
    print(f"[log] - {s}")


def gen_json(audio_paths: list[Path] | Generator[Path, None, None], out_file: Path):
    out_file = Path(out_file)
    d = {}
    for audio_p in audio_paths:
        log(f"Segment '{audio_p.name}'")

        assert audio_p.exists()
        d[audio_p.stem] = {
            "wav": str(audio_p.resolve()),
            "label": "",
        }

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w") as f:
        json.dump(d, f, indent=4)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--audio",
        "-a",
        help="Folder containing a list of audio files or a single audio file (in .wav format).",
    )
    parser.add_argument(
        "--output", "-o", default="json/audio_chunks", help="Name of the output file."
    )

    args = parser.parse_args()

    audio = Path(args.audio)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if audio.is_dir():
        log("is dir :)")
        audio_paths = audio.glob("*.wav")
    elif audio.is_file() and audio.suffix == ".wav":
        log("is a single file :)")
        audio_paths = [audio]

    log("Starting generation")
    gen_json(audio_paths, out_file=out_path.with_suffix(".json"))
