import numpy as np

class ReliabilityModel:
    def __init__(self, weights=None):
        self.weights = weights or {
            "sensor_integrity": 0.25,
            "classification_confidence": 0.25,
            "fusion_quality": 0.25,
            "datalink": 0.25
        }

    def compute_rho(self, inputs: dict) -> float:
        score = 0.0
        for key, weight in self.weights.items():
            score += weight * inputs.get(key, 0.0)
        return np.clip(score, 0.0, 1.0)

    def autonomy_level(self, rho: float) -> str:
        if rho >= 0.80:
            return "AUTONOMOUS"
        elif rho >= 0.40:
            return "ADVISE"
        else:
            return "DEFER"