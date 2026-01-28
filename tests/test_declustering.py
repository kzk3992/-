import datetime as dt

from src.detect_swans import Detection, decluster_detections


def test_declustering_merges_within_window():
    detections = [
        Detection(dt.datetime(2024, 1, 1, 9, 0), 60),
        Detection(dt.datetime(2024, 1, 1, 9, 10), -55),
        Detection(dt.datetime(2024, 1, 1, 9, 25), 80),
        Detection(dt.datetime(2024, 1, 1, 10, 0), -70),
    ]
    clustered = decluster_detections(detections, decluster_minutes=30)
    assert len(clustered) == 2
    assert clustered[0].timestamp == dt.datetime(2024, 1, 1, 9, 0)
    assert clustered[1].timestamp == dt.datetime(2024, 1, 1, 10, 0)
