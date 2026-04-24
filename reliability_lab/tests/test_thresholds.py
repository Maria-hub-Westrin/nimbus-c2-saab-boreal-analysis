from rho_sa_model import ReliabilityModel

def test_autonomy_levels():
    model = ReliabilityModel()
    assert model.autonomy_level(0.9) == "AUTONOMOUS"
    assert model.autonomy_level(0.5) == "ADVISE"
    assert model.autonomy_level(0.2) == "DEFER"