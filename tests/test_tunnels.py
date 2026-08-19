import unittest
from types import SimpleNamespace
from unittest.mock import patch

from stoatswarm import TunnelConfig, generate_tunnel


class TunnelGenerationTests(unittest.TestCase):
    def test_same_seed_produces_identical_world(self) -> None:
        first = generate_tunnel(8675309)
        second = generate_tunnel(8675309)
        self.assertEqual(first.cells, second.cells)
        self.assertEqual(first.edges, second.edges)

    def test_different_seeds_produce_different_worlds(self) -> None:
        first = generate_tunnel(1)
        second = generate_tunnel(2)
        self.assertNotEqual((first.cells, first.edges), (second.cells, second.edges))

    def test_generated_world_is_connected_and_correct_size(self) -> None:
        config = TunnelConfig(grid_width=15, grid_height=17, target_cells=80)
        for seed in range(50):
            with self.subTest(seed=seed):
                tunnel = generate_tunnel(seed, config)
                tunnel.validate()
                self.assertEqual(len(tunnel.cells), config.target_cells)

    def test_generator_can_fill_entire_even_sized_grid(self) -> None:
        config = TunnelConfig(grid_width=4, grid_height=6, target_cells=24)
        tunnel = generate_tunnel(42, config)
        self.assertEqual(len(tunnel.cells), 24)

    def test_invalid_configuration_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            generate_tunnel(1, TunnelConfig(target_cells=1))

    def test_coverage_route_visits_every_cell_and_uses_valid_edges(self) -> None:
        from stoatswarm.video import coverage_route

        tunnel = generate_tunnel(2026, TunnelConfig(target_cells=50))
        route = coverage_route(tunnel)
        self.assertEqual(route[0], tunnel.entrance)
        self.assertEqual(set(route), set(tunnel.cells))
        for first, second in zip(route, route[1:]):
            self.assertIn(second, tunnel.neighbors(first))

    def test_pybullet_adapter_builds_static_geometry(self) -> None:
        from stoatswarm.pybullet_world import build_pybullet_world

        calls: list[tuple[str, dict]] = []

        def record(name: str):
            def fake(*args, **kwargs):
                calls.append((name, kwargs))
                return len(calls)

            return fake

        fake_pybullet = SimpleNamespace(
            GEOM_BOX=1,
            createCollisionShape=record("collision"),
            createVisualShape=record("visual"),
            createMultiBody=record("body"),
        )
        tunnel = generate_tunnel(7, TunnelConfig(target_cells=8))
        with patch.dict("sys.modules", {"pybullet": fake_pybullet}):
            bodies = build_pybullet_world(tunnel, client_id=3)

        self.assertGreater(len(bodies), len(tunnel.cells) * 2)
        self.assertEqual(len(bodies), sum(name == "body" for name, _ in calls))
        self.assertTrue(all(kwargs["physicsClientId"] == 3 for _, kwargs in calls))


if __name__ == "__main__":
    unittest.main()
