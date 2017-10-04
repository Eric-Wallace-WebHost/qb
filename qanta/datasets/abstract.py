from abc import ABCMeta, abstractmethod
from typing import Tuple, List, Any

QuestionText = str
Answer = str
Evidence = Any
TrainingData = Tuple[List[List[QuestionText]], List[Answer], List[Evidence]]


class AbstractDataset(metaclass=ABCMeta):
    def __init__(self):
        pass

    @abstractmethod
    def training_data(self) -> TrainingData:
        pass
