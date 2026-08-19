"""Headless PyBullet video rendering for generated tunnels."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .tunnels import Cell, TunnelMap

if TYPE_CHECKING:
    from os import PathLike


def coverage_route(tunnel: TunnelMap) -> tuple[Cell, ...]:
    """Return a deterministic walk that visits every cell at least once.

    A depth-first traversal naturally backtracks out of dead ends, which makes
    the video resemble an explorer methodically covering the tunnel network.
    """
    route = [tunnel.entrance]
    visited = {tunnel.entrance}

    def visit(cell: Cell) -> None:
        for neighbor in tunnel.neighbors(cell):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            route.append(neighbor)
            visit(neighbor)
            route.append(cell)

    visit(tunnel.entrance)
    if visited != set(tunnel.cells):
        raise ValueError("cannot create coverage route for a disconnected tunnel")
    return tuple(route)


def render_exploration_video(
    tunnel: TunnelMap,
    output: str | PathLike[str],
    *,
    width: int = 640,
    height: int = 360,
    fps: int = 24,
    seconds_per_cell: float = 0.45,
) -> Path:
    """Render a first-person coverage walk to an MP4 using TinyRenderer."""
    if width <= 0 or height <= 0 or fps <= 0 or seconds_per_cell <= 0:
        raise ValueError("video dimensions, fps, and timing must be positive")
    try:
        import imageio.v2 as imageio
        import numpy as np
        import pybullet as p
    except ImportError as exc:  # pragma: no cover - optional runtime dependencies
        raise RuntimeError("Install video dependencies with: pip install -e .[video]") from exc

    from .pybullet_world import build_pybullet_world

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    route = coverage_route(tunnel)
    cfg = tunnel.config
    camera_z = min(1.25, cfg.tunnel_height * 0.55)
    frames_per_leg = max(2, round(fps * seconds_per_cell))
    projection = p.computeProjectionMatrixFOV(
        fov=78,
        aspect=width / height,
        nearVal=0.05,
        farVal=max(cfg.grid_width, cfg.grid_height) * cfg.cell_size,
    )

    client = p.connect(p.DIRECT)
    writer = None
    try:
        p.setGravity(0, 0, -9.81, physicsClientId=client)
        build_pybullet_world(tunnel, client)
        writer = imageio.get_writer(
            output_path,
            fps=fps,
            codec="libx264",
            quality=7,
            macro_block_size=None,
        )

        for start, end in zip(route, route[1:]):
            sx, sy = start[0] * cfg.cell_size, start[1] * cfg.cell_size
            ex, ey = end[0] * cfg.cell_size, end[1] * cfg.cell_size
            for frame_index in range(frames_per_leg):
                alpha = frame_index / frames_per_leg
                # Smooth acceleration avoids a mechanical stop-start appearance.
                smooth = alpha * alpha * (3.0 - 2.0 * alpha)
                eye = (sx + (ex - sx) * smooth, sy + (ey - sy) * smooth, camera_z)
                target = (eye[0] + ex - sx, eye[1] + ey - sy, camera_z)
                view = p.computeViewMatrix(eye, target, (0, 0, 1))
                _, _, rgba, _, _ = p.getCameraImage(
                    width,
                    height,
                    viewMatrix=view,
                    projectionMatrix=projection,
                    renderer=p.ER_TINY_RENDERER,
                    lightDirection=(-0.4, -0.6, -1.0),
                    shadow=1,
                    physicsClientId=client,
                )
                frame = np.asarray(rgba, dtype=np.uint8).reshape(height, width, 4)[..., :3]
                writer.append_data(frame)

        # Hold briefly on the entrance after completing the coverage traversal.
        if len(route) > 1:
            previous, final = route[-2], route[-1]
            eye = (final[0] * cfg.cell_size, final[1] * cfg.cell_size, camera_z)
            target = (
                eye[0] + (final[0] - previous[0]) * cfg.cell_size,
                eye[1] + (final[1] - previous[1]) * cfg.cell_size,
                camera_z,
            )
            view = p.computeViewMatrix(eye, target, (0, 0, 1))
            _, _, rgba, _, _ = p.getCameraImage(
                width,
                height,
                viewMatrix=view,
                projectionMatrix=projection,
                renderer=p.ER_TINY_RENDERER,
                physicsClientId=client,
            )
            frame = np.asarray(rgba, dtype=np.uint8).reshape(height, width, 4)[..., :3]
            for _ in range(fps // 2):
                writer.append_data(frame)
    finally:
        if writer is not None:
            writer.close()
        if p.isConnected(client):
            p.disconnect(client)

    return output_path
