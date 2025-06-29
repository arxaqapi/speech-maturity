# Speech Maturity Classifier

## Installation Steps
1. ensure git-lfs is installed
2. `git clone --recurse-submodules https://github.com/arxaqapi/vocal-dumpster`
3. run `uv sync`

## Usage

### Inference
```sh
$ uv run scripts/infer.py hparams/hparams.yaml
```
Or even better, use the `run.sh` script that fixes a lot of problems.

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

