from rho_sa_model import ReliabilityModel

def test_rho_bounds():
    model = ReliabilityModel()
    inputs = {
        "sensor_integrity": 1,
        "classification_confidence": 1,
        "fusion_quality": 1,
        "datalink": 1
    }
    rho = model.compute_rho(inputs)
    assert 0.0 <= rho <= 1.0