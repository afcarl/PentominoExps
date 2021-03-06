import abc
from abc import ABCMeta

import os

from collections import defaultdict
import logging
import cPickle as pkl

import numpy as np

from utils.utils import ensure_dir_exists
from .commons import SAVE_DUMP_FOLDER

logger = logging.getLogger(__name__)


class Basic(object):

    def merge_params(self):
        if not hasattr(self, 'children') and self.children is None:
            raise ValueError("Children layers should not be empty.")
        if self.children:
            self.params = sum(child.params if hasattr(child, "params")\
                    else [child] for child in self.children)

    def pname(self, newname):
        return self.name + "_" + newname

    def str_params(self, logger=None):
        if logger is not None:
            for param in self.params.values:
                pshape = param.get_value().shape
                msg = "Parameter: %s, param shape: " % param.name
                logger.info(msg + str(pshape))
            logger.info("Total number of params is, %d " % self.params.total_nparams())


class AbstractModel(object):
    __metaclass__ = ABCMeta
    @abc.abstractmethod
    def build_model(self):
        pass

    @abc.abstractmethod
    def get_cost(self):
        pass

    @abc.abstractmethod
    def get_inspect_fn(self):
        pass

    @abc.abstractmethod
    def get_valid_fn(self):
        pass

    @abc.abstractmethod
    def get_train_fn(self):
        pass

    @abc.abstractmethod
    def fprop(self):
        pass


class Model(AbstractModel, Basic):
    def __init__(self):
        pass


class MainLoop(object):

    def __init__(self, model,
                 learning_rate,
                 print_every=None,
                 checkpoint_every=None,
                 inspect_every=None,
                 validate_every=None,
                 train_data_gen=None,
                 valid_data_gen=None,
                 train_mon_data_gen=None,
                 reload_model=False,
                 monitor_full_train=False,
                 inspect_only=True,
                 inspect_model=False,
                 max_iters=None,
                 valid_iters=False,
                 prefix=None):

        self.model = model
        self.learning_rate = learning_rate
        self.print_every = print_every
        self.train_mon_data_gen = train_mon_data_gen
        self.train_data_gen = train_data_gen
        self.valid_data_gen = valid_data_gen
        self.checkpoint_every = checkpoint_every
        self.validate_every = validate_every
        self.reload_model = reload_model
        self.inspect_only = inspect_only
        self.prefix = prefix

        self.patience = 1
        self.inc_ratio = 0.001
        self.prev_error = np.inf
        self.cur_patience = 0
        self.valid_iters = valid_iters
        self.model_inspection = inspect_model
        self.inspect_every = inspect_every
        self.monitor_full_train = monitor_full_train

        self.mdl_name = self.prefix + "_model_params.pkl"
        self.stats_name = self.prefix + "_stats.pkl"
        self.best_mdl_name = self.prefix + "_best_model_params.pkl"
        self.best_stats_name = self.prefix + "_best_stats.pkl"

        if (self.train_mon_data_gen is not None) ^ self.monitor_full_train:
            raise RuntimeError

        self.best_cost = np.inf
        self.best_error = np.inf

        self.stats = defaultdict(list)
        self.max_iters = max_iters
        self.train_fn = None
        self.valid_fn = None
        self.cnt = 0

    def prepare_model(self):
        if self.reload_model:
            logger.info("Reloading stats from %s." % self.mdl_name)
            if not self.model_inspection:
                self.stats = pkl.load(open(self.stats_name, "rb"))
        mdl_name = self.mdl_name if self.reload_model else None

        if not self.inspect_only:
            self.train_fn = self.model.get_train_fn(lr=self.learning_rate,
                                                    mdl_name=mdl_name)

        if self.validate_every and not self.inspect_only:
            self.valid_fn = self.model.get_valid_fn(mdl_name=mdl_name)

        if self.inspect_every or self.inspect_only:
            self.inspect_fn = self.model.get_inspect_fn(mdl_name=mdl_name)

    def save(self, mdl_name=None, stats_name=None):
        if mdl_name is None:
            mdl_name = self.mdl_name

        if stats_name is None:
            stats_name = self.stats_name

        logger.info("Saving the model to %s." % mdl_name)
        ensure_dir_exists(SAVE_DUMP_FOLDER)
        mdl_path = os.path.join(SAVE_DUMP_FOLDER, mdl_name)
        stats_path = os.path.join(SAVE_DUMP_FOLDER, stats_name)
        self.model.params.save(mdl_path)
        pkl.dump(self.stats, open(stats_path, 'wb'), 2)

    def run(self):
        running = True
        logger.info("Started running...")

        while running:
            if self.validate_every:
                if self.cnt % self.validate_every == 0:
                    self.validate()
                    if self.monitor_full_train:
                        self.validate(data_gen=self.train_mon_data_gen, mode="Train")

            self.train()
            if (self.inspect_every is not None and
                self.cnt % self.inspect_every == 0 and self.model_inspection):
                self.inspect_model()

            if self.cnt % self.checkpoint_every == 0:
                self.save()

            if self.cnt >= self.max_iters:
                running = False

            self.cnt += 1

    def train(self):
        raise NotImplementedError

    def validate(self, data_gen=None, mode="Valid"):
        raise NotImplementedError

    def inspect_model(self):
        raise NotImplementedError

