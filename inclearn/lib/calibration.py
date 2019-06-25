import torch
from torch import nn, optim
from torch.nn import functional as F

from inclearn.lib.network import (CalibrationWrapper, LinearModel,
                                  TemperatureScaling)


def calibrate(network, loader, device, indexes, calibration_type="linear"):
    """Corrects the bias for new classes.

    :param network: The logits extractor model, usually convnet+FC w/o final act.
    :param loader: The validation data loader.
    :param device: Device on which apply the computation.
    :param indexes: A list of tuple made a starting and ending indexes. They delimit
                    on which range of targets to apply the calibration. If given
                    several tuples, different models will be used per range.
    :return: A wrapper `CalibrationWrapper`.
    """
    logits, labels = _extract_data(network, loader, device)
    calibration_wrapper = _get_calibration_model(indexes, calibration_type).to(device)

    def eval():
        corrected_logits = calibration_wrapper(logits)
        loss = F.cross_entropy(corrected_logits, labels)
        loss.backward()
        return loss

    optimizer = optim.LBFGS(calibration_wrapper.parameters(), lr=0.01, max_iter=50)
    optimizer.step(eval)

    return calibration_wrapper

class LinearModelBis(nn.Module):
    def __init__(self, start_index, alpha=1., beta=0.):
        super().__init__()

        self.alpha = nn.Parameter(torch.tensor(alpha))
        self.beta = nn.Parameter(torch.tensor(beta))
        self.start = start_index

    def forward(self, inputs):
        return torch.cat((
            inputs[..., :self.start],
            self.alpha * inputs[..., self.start:] + self.beta
        ), dim=1)

def _get_calibration_model(indexes, calibration_type):
    #print("start idx", indexes[0][0])
    #return LinearModelBis(indexes[0][0])

    calibration_wrapper = CalibrationWrapper()

    for start_index, end_index in indexes:
        if calibration_type == "linear":
            model = LinearModel(alpha=1., beta=0.)
        elif calibration_type == "temperature":
            model = TemperatureScaling(temperature=1.)
        else:
            raise ValueError("Unknown calibration model {}.".format(calibration_type))

        calibration_wrapper.add_model(model, start_index, end_index)

    return calibration_wrapper


def _extract_data(network, loader, device):
    logits = []
    labels = []

    with torch.no_grad():
        for inputs, targets in loader:
            logits.append(network(inputs.to(device)))
            labels.append(targets.to(device))

        logits = torch.cat(logits).to(device)
        labels = torch.cat(labels).to(device)

    return logits, labels
