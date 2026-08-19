# StoatSwarm

Train a drone swarm to autonomously explore tunnels and indoor structures.

The first project component is a deterministic, graph-first tunnel generator.
It creates connected modular tunnel layouts from integer seeds and can turn
them into simple static PyBullet geometry.

## Quick start

```powershell
python -m pip install -e .
stoatswarm-tunnel --seed 12345
python -m unittest discover -s tests
```

To inspect the generated tunnel in PyBullet:

```powershell
python -m pip install -e ".[simulation]"
stoatswarm-tunnel --seed 12345 --simulate
```

## Headless MP4 rendering with Docker

The Docker image runs PyBullet without a display, walks a first-person camera
through every reachable tunnel cell, and writes an H.264 MP4:

```powershell
docker build -t stoatswarm .
New-Item -ItemType Directory -Force output
docker run --rm -v "${PWD}/output:/output" stoatswarm --seed 12345 --cells 30 --video /output/tunnel-12345.mp4
```

Change `--seed` to produce a different deterministic world. Rendering can be
tuned with `--video-width`, `--video-height`, `--video-fps`, and
`--seconds-per-cell`.

The same seed and configuration always produce the same cells and connections.
Use `--cells`, `--branch-probability`, and `--loop-probability` to adjust the
topology.
