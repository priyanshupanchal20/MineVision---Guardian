import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from minevision.fusion.distance import Zone, classify_zone, distance_risk
from minevision.fusion.engine import FuseInput, fuse, risk_label
from minevision.safety import decide
from minevision.fusion.fog import dew_point_c, fog_mode_next, fog_risk_index, humidity_term
from minevision.vision import visibility_from_gray, synthetic_scene
from minevision.thermal import ThermalAnalyzer, synthetic_frame


def test_humidity_piecewise():
    assert humidity_term(30) == 0
    assert abs(humidity_term(60) - 20) < 0.01
    assert humidity_term(95) == 100


def test_dew_point_humid_is_close():
    td = dew_point_c(24.0, 95.0)
    assert 22.0 < td < 24.0


def test_fog_clear_vs_dense():
    clear = fog_risk_index(30, 45, 10, 0.9)
    dense = fog_risk_index(22, 96, 80, 0.15)
    assert clear.index <= 30
    assert dense.index >= 70
    assert clear.label == "Clear"
    assert "fog" in dense.label.lower() or "Severe" in dense.label or "Dense" in dense.label


def test_fog_hysteresis():
    assert fog_mode_next(70, False) is True
    assert fog_mode_next(65, True) is True
    assert fog_mode_next(59, True) is False


def test_zones():
    assert classify_zone(12) == Zone.SAFE
    assert classify_zone(6) == Zone.WARNING
    assert classify_zone(3.0) == Zone.WARNING  # LiDAR 3 m is above 1.5 m DANGER
    assert classify_zone(1.2) == Zone.DANGER
    assert classify_zone(1.2, danger_m=1.0) == Zone.WARNING
    assert classify_zone(0.8, danger_m=1.0) == Zone.DANGER
    assert classify_zone(None) == Zone.UNKNOWN


def test_danger_floor_critical():
    r = fuse(
        FuseInput(
            front_m=1.2,
            left_m=6,
            right_m=6,
            temperature_c=28,
            humidity_rh=50,
            darkness_score=20,
            visibility_confidence=0.8,
            thermal_anomaly=False,
            thermal_risk=5,
            motion_detected=False,
        )
    )
    assert r.front_zone == Zone.DANGER
    assert r.risk_score >= 81
    assert r.risk_level == "CRITICAL"
    assert r.speed_advice == "STOP VEHICLE"


def test_lidar_3m_is_not_danger():
    r = fuse(
        FuseInput(
            front_m=3.0,
            left_m=6,
            right_m=6,
            temperature_c=28,
            humidity_rh=50,
            darkness_score=20,
            visibility_confidence=0.8,
            thermal_anomaly=False,
            thermal_risk=5,
            motion_detected=False,
        )
    )
    assert r.front_zone == Zone.WARNING
    assert r.left_zone != Zone.DANGER
    assert r.right_zone != Zone.DANGER
    d = decide("DUMPER_01", r, 3.0, 6, 6)
    assert d.audio == "off"


def test_fog_plus_obstacle_high_risk():
    r = fuse(
        FuseInput(
            front_m=5.0,
            left_m=6,
            right_m=6,
            temperature_c=21,
            humidity_rh=97,
            darkness_score=85,
            visibility_confidence=0.12,
            thermal_anomaly=False,
            thermal_risk=5,
            motion_detected=False,
            fog_mode_prev=True,
        )
    )
    assert r.fog.index > 70
    assert r.risk_score >= 61
    assert r.fog_mode is True
    assert r.speed_advice != "NORMAL SPEED"


def test_presence_agreement():
    r = fuse(
        FuseInput(
            front_m=9.0,
            left_m=5,
            right_m=6,
            temperature_c=27,
            humidity_rh=55,
            darkness_score=40,
            visibility_confidence=0.6,
            thermal_anomaly=True,
            thermal_risk=50,
            motion_detected=True,
        )
    )
    assert r.presence == "HIGH CONFIDENCE PRESENCE"
    assert r.risk_score >= 61


def test_three_sensor_bonus():
    r = fuse(
        FuseInput(
            front_m=3.9,
            left_m=6,
            right_m=6,
            temperature_c=27,
            humidity_rh=50,
            darkness_score=30,
            visibility_confidence=0.7,
            thermal_anomaly=True,
            thermal_risk=40,
            motion_detected=True,
            lidar_strength=300,
        )
    )
    assert r.agreement_bonus == 12


def test_labels():
    assert risk_label(10) == "SAFE"
    assert risk_label(40) == "CAUTION"
    assert risk_label(70) == "HIGH RISK"
    assert risk_label(90) == "CRITICAL"


def test_visibility_fog_lowers_confidence():
    clear = visibility_from_gray(synthetic_scene(0.05))
    foggy = visibility_from_gray(synthetic_scene(0.95))
    assert clear.confidence > foggy.confidence


def test_thermal_blob():
    a = ThermalAnalyzer()
    # warmup on ambient
    for _ in range(5):
        a.process(synthetic_frame(26.0, hot_blob=False))
    r = a.process(synthetic_frame(26.0, hot_blob=True, blob_c=36.0))
    assert r.anomaly is True
    assert r.max_c > 30


def test_distance_risk_monotonic():
    far, *_ = distance_risk(12, 6, 6, False)
    near, *_ = distance_risk(2, 6, 6, False)
    assert near > far


def test_buzzer_lidar_1_5_and_us_1_0():
    r = fuse(
        FuseInput(
            front_m=2.5,
            left_m=2.7,
            right_m=2.4,
            temperature_c=28,
            humidity_rh=50,
            darkness_score=20,
            visibility_confidence=0.8,
            thermal_anomaly=False,
            thermal_risk=5,
            motion_detected=False,
        )
    )
    assert decide("DUMPER_01", r, 2.5, 2.7, 2.4).audio == "off"
    assert decide("DUMPER_01", r, 1.2, 2.7, 2.4).audio == "continuous"
    assert decide("DUMPER_01", r, 3.0, 0.9, 2.4).audio == "continuous"
    assert decide("DUMPER_01", r, 3.0, 2.0, 0.8).audio == "continuous"
    assert decide("DUMPER_01", r, 3.0, 1.2, 1.2).audio == "off"


def test_missing_left_us_is_not_obstacle():
    from minevision.fusion.distance import component_risk

    assert component_risk(None, False) == 5.0
    r = fuse(
        FuseInput(
            front_m=9.0,
            left_m=None,
            right_m=6.0,
            temperature_c=28,
            humidity_rh=50,
            darkness_score=20,
            visibility_confidence=0.8,
            thermal_anomaly=False,
            thermal_risk=5,
            motion_detected=False,
        )
    )
    assert r.left_zone == Zone.UNKNOWN
    assert r.risk_score < 81
    assert r.risk_level != "CRITICAL"
    assert any("Left ultrasonic" in n for n in r.notes)


def test_close_lidar_is_danger():
    assert classify_zone(0.07) == Zone.DANGER
    assert classify_zone(0.4) == Zone.DANGER


def test_pi_camera_pins():
    from minevision import config

    assert config.PI_MLX_VIN_PHYS == 1
    assert config.PI_MLX_GND_PHYS == 6
    assert config.PI_MLX_SDA_PHYS == 3
    assert config.PI_MLX_SCL_PHYS == 5
    assert config.PI_MLX_SDA_BCM == 2
    assert config.PI_OV_VCC_PHYS == 17
    assert config.PI_OV_GND_PHYS == 9
    assert config.PI_OV_SIOD_BCM == 10
    assert config.PI_OV_SIOC_BCM == 11
    assert config.PI_OV_XCLK_BCM == 4
    assert config.PI_OV_D_BCM == (5, 6, 13, 19, 26, 16, 20, 21)
    assert config.PI_OV_WIDTH == 320
    assert config.PI_OV_HEIGHT == 240
    ov = {
        config.PI_OV_SIOD_BCM,
        config.PI_OV_SIOC_BCM,
        config.PI_OV_XCLK_BCM,
        config.PI_OV_PCLK_BCM,
        config.PI_OV_VSYNC_BCM,
        config.PI_OV_HREF_BCM,
        config.PI_OV_RESET_BCM,
        config.PI_OV_PWDN_BCM,
        *config.PI_OV_D_BCM,
    }
    mlx = {config.PI_MLX_SDA_BCM, config.PI_MLX_SCL_BCM}
    tft = {
        config.PI_ST_SCK_BCM,
        config.PI_ST_MOSI_BCM,
        config.PI_ST_CS_BCM,
        config.PI_ST_DC_BCM,
        config.PI_ST_RST_BCM,
        config.PI_ST_MISO_BCM,
    }
    assert ov.isdisjoint(mlx)
    assert ov.isdisjoint(tft)
    assert mlx.isdisjoint(tft)
    assert 50_000 <= config.PI_ST_BAUD <= 500_000


def test_yuyv_luma_is_even_bytes():
    from minevision.vision.ov7670 import yuyv_to_gray

    buf = bytes([10, 99, 20, 88, 30, 77, 40, 66])
    gray = yuyv_to_gray(buf, width=2, height=2)
    assert gray.shape == (2, 2)
    assert abs(float(gray[0, 0]) - 10 / 255) < 1e-6
    assert abs(float(gray[0, 1]) - 20 / 255) < 1e-6


def test_scene_score_rejects_static():
    import numpy as np
    from minevision.vision import synthetic_scene
    from minevision.vision.ov7670 import spatial_score

    scene = synthetic_scene(0.1)
    noise = np.random.default_rng(0).random((120, 160)).astype(np.float32)
    assert spatial_score(scene) > 0.4
    assert spatial_score(noise) < spatial_score(scene)


def test_gray_to_png_header():
    from minevision.vision import gray_to_png, rgb_to_png, synthetic_scene
    import numpy as np

    png = gray_to_png(synthetic_scene(0.2))
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"IEND" in png[-16:]
    color = np.zeros((8, 8, 3), dtype=np.float32)
    color[..., 0] = 0.8
    color[..., 1] = 0.2
    color[..., 2] = 0.1
    cpng = rgb_to_png(color)
    assert cpng.startswith(b"\x89PNG\r\n\x1a\n")
    assert cpng[25] == 2  # RGB colour type in IHDR


def test_yuyv_to_rgb_is_not_gray():
    from minevision.vision.ov7670 import yuyv_to_rgb
    import numpy as np

    # Mid luma, U=80 (blue-ish), V=180 (red-ish)
    row = np.array([128, 80, 128, 180] * 4, dtype=np.uint8)
    buf = np.tile(row, 8)
    rgb = yuyv_to_rgb(buf.tobytes(), width=8, height=8)
    assert rgb.shape == (8, 8, 3)
    assert float(rgb[..., 0].mean()) != float(rgb[..., 2].mean())


def test_st7735_gray_to_rgb565():
    import numpy as np
    from minevision.vision.st7735 import fit_square, gray_to_rgb565

    src = np.linspace(0, 1, 320 * 240, dtype=np.float32).reshape(240, 320)
    small = fit_square(src)
    assert small.shape == (240, 240)
    buf = gray_to_rgb565(small)
    assert len(buf) == 240 * 240 * 2
    black = gray_to_rgb565(np.zeros((2, 2), dtype=np.float32))
    assert black == b"\x00\x00" * 4
    white = gray_to_rgb565(np.ones((1, 1), dtype=np.float32))
    assert white == b"\xff\xff"


def test_gc9a01_compose_dual_camera_and_thermal():
    import numpy as np
    from minevision.vision.st7735 import compose_dual, rgb_to_rgb565

    gray = np.full((240, 320), 0.7, dtype=np.float32)
    temps = np.linspace(20, 80, 24 * 32, dtype=np.float32).reshape(24, 32)
    rgb = compose_dual(gray, temps, 240)
    assert rgb.shape == (240, 240, 3)
    assert float(rgb[40, 120].mean()) > 0.4
    assert float(rgb[200, 200, 0]) > float(rgb[200, 20, 0])
    buf = rgb_to_rgb565(rgb)
    assert len(buf) == 240 * 240 * 2


def test_dashboard_urls_use_stable_name():
    from minevision.netinfo import LAN_NAME, dashboard_urls

    urls = dashboard_urls(8000)
    assert any(f"{LAN_NAME}.local:8000" in u for u in urls)
