"""Command-line preview and PyBullet demo."""

from __future__ import annotations

import argparse
import time

from .tunnels import TunnelConfig, generate_tunnel


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a deterministic tunnel world")
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--cells", type=int, default=60)
    parser.add_argument("--width", type=int, default=25)
    parser.add_argument("--height", type=int, default=25)
    parser.add_argument("--branch-probability", type=float, default=0.22)
    parser.add_argument("--loop-probability", type=float, default=0.08)
    parser.add_argument("--simulate", action="store_true", help="open the tunnel in the PyBullet GUI")
    parser.add_argument("--video", type=str, help="render a headless MP4 to this path")
    parser.add_argument("--video-width", type=int, default=640)
    parser.add_argument("--video-height", type=int, default=360)
    parser.add_argument("--video-fps", type=int, default=24)
    parser.add_argument("--seconds-per-cell", type=float, default=0.45)
    return parser


def main() -> None:
    args = _parser().parse_args()
    config = TunnelConfig(
        grid_width=args.width,
        grid_height=args.height,
        target_cells=args.cells,
        branch_probability=args.branch_probability,
        loop_probability=args.loop_probability,
    )
    tunnel = generate_tunnel(args.seed, config)
    print(tunnel.to_ascii())
    print(f"\nseed={tunnel.seed} cells={len(tunnel.cells)} edges={len(tunnel.edges)} junctions={len(tunnel.junctions)} exits={len(tunnel.exits)}")

    if args.video:
        from .video import render_exploration_video

        output = render_exploration_video(
            tunnel,
            args.video,
            width=args.video_width,
            height=args.video_height,
            fps=args.video_fps,
            seconds_per_cell=args.seconds_per_cell,
        )
        print(f"Rendered exploration video: {output}")

    if args.simulate:
        try:
            import pybullet as p
        except ImportError as exc:
            raise SystemExit("Install simulation dependencies with: pip install -e .[simulation]") from exc
        from .pybullet_world import build_pybullet_world

        client = p.connect(p.GUI)
        p.setGravity(0, 0, -9.81, physicsClientId=client)
        build_pybullet_world(tunnel, client)
        p.resetDebugVisualizerCamera(35, 45, -55, (0, 0, 0), physicsClientId=client)
        try:
            while p.isConnected(client):
                p.stepSimulation(physicsClientId=client)
                time.sleep(1 / 240)
        except KeyboardInterrupt:
            pass
        finally:
            if p.isConnected(client):
                p.disconnect(client)


if __name__ == "__main__":
    main()
