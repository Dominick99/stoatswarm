"""PyBullet adapter for generated tunnel maps."""

from __future__ import annotations

from .tunnels import Cell, TunnelMap, _DIRECTIONS, _canonical_edge


def build_pybullet_world(tunnel: TunnelMap, client_id: int = 0) -> list[int]:
    """Create static floors, ceilings, and walls and return their body IDs."""
    try:
        import pybullet as p
    except ImportError as exc:  # pragma: no cover - depends on optional package
        raise RuntimeError("Install simulation dependencies with: pip install -e .[simulation]") from exc

    cfg = tunnel.config
    bodies: list[int] = []
    wall_segments: set[tuple[Cell, Cell]] = set()

    def add_box(half_extents: tuple[float, float, float], position: tuple[float, float, float], color: tuple[float, float, float, float]) -> None:
        collision = p.createCollisionShape(p.GEOM_BOX, halfExtents=half_extents, physicsClientId=client_id)
        visual = p.createVisualShape(p.GEOM_BOX, halfExtents=half_extents, rgbaColor=color, physicsClientId=client_id)
        bodies.append(p.createMultiBody(baseMass=0, baseCollisionShapeIndex=collision, baseVisualShapeIndex=visual, basePosition=position, physicsClientId=client_id))

    for x, y in sorted(tunnel.cells):
        cx, cy = x * cfg.cell_size, y * cfg.cell_size
        add_box((cfg.cell_size / 2, cfg.cell_size / 2, cfg.wall_thickness / 2), (cx, cy, -cfg.wall_thickness / 2), (0.32, 0.30, 0.27, 1))
        add_box((cfg.cell_size / 2, cfg.cell_size / 2, cfg.wall_thickness / 2), (cx, cy, cfg.tunnel_height + cfg.wall_thickness / 2), (0.24, 0.23, 0.22, 1))

        for dx, dy in _DIRECTIONS:
            neighbor = (x + dx, y + dy)
            if _canonical_edge((x, y), neighbor) in tunnel.edges:
                continue
            segment = _canonical_edge((x, y), neighbor)
            if segment in wall_segments:
                continue
            wall_segments.add(segment)
            if dx:
                position = (cx + dx * cfg.cell_size / 2, cy, cfg.tunnel_height / 2)
                half_extents = (cfg.wall_thickness / 2, cfg.cell_size / 2, cfg.tunnel_height / 2)
            else:
                position = (cx, cy + dy * cfg.cell_size / 2, cfg.tunnel_height / 2)
                half_extents = (cfg.cell_size / 2, cfg.wall_thickness / 2, cfg.tunnel_height / 2)
            add_box(half_extents, position, (0.42, 0.39, 0.34, 1))
    return bodies
