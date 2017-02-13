from clatoolkit.models import UnitOffering
from models import al2_classifier as c


class ActiveLearning_Squared(object):

    def __init__(self, unit_id):
        self.classification_models = UnitOffering.get_al_classifiers()

    def train_(construct):
        for model_id in self.classification_models:
            classifier = c.objects.get(id=model_id)

            if classifier.construct == construct:
                # train this model on the unit's reclassifications
                pass

        # there is no existing classifier for this construct in this unit
