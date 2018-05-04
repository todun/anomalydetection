# -*- coding:utf-8 -*- #
import logging
from typing import List

from anomalydetection.backend.engine.base_engine import BaseEngine
from anomalydetection.backend.entities import BaseMessageHandler
from anomalydetection.backend.entities.output_message import OutputMessage
from anomalydetection.backend.store_middleware import Middleware
from anomalydetection.backend.stream import BaseStreamBackend, \
    BaseObservable


class StreamEngineInteractor(object):

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    DEFAULT_AGG_WINDOW = 5 * 60 * 1000
    DEFAULT_AGG_FUNCTION = sum

    def __init__(self,
                 stream: BaseStreamBackend,
                 engine: BaseEngine,
                 message_handler: BaseMessageHandler,
                 middleware: List[Middleware] = [],
                 warm_up: BaseObservable = None,
                 agg_function: callable = DEFAULT_AGG_FUNCTION,
                 agg_window_millis: int = DEFAULT_AGG_WINDOW) -> None:
        super().__init__()
        self.stream = stream
        self.engine = engine
        self.middleware = middleware
        self.warm_up = warm_up
        self.message_handler = message_handler
        self.agg_function = agg_function
        self.agg_window_millis = agg_window_millis

    def build_output_message(self, value):
        input_message, agg_value = value
        output = {
            "application": input_message.application,
            "agg_value": agg_value,
            "agg_function": str(self.agg_function),
            "agg_window_millis": self.agg_window_millis,
            "ts": str(self.message_handler.extract_ts(input_message)),
            "anomaly_results": self.engine.predict(agg_value)
        }
        return OutputMessage(**output)

    def zip_input_with_agg(self, value):
        return (
            value[-1],
            self.agg_function(
                map(self.message_handler.extract_value, value))
        )

    def run(self):

        if self.warm_up:
            warm_up = self.warm_up.get_observable() \
                .map(lambda x: self.build_output_message((x.to_input(),
                                                          x.agg_value))) \
                .to_blocking()
            len([x for x in warm_up])  # Force model to consume messages
            self.logger.info("Warm up completed.")

        # Aggregate and map input values.
        stream = self.stream.get_observable() \
            .map(lambda x: self.message_handler.parse_message(x)) \
            .filter(lambda x: self.message_handler.validate_message(x)) \

        rx = stream \
            .buffer_with_time(timespan=self.agg_window_millis) \
            .filter(lambda x: x) \
            .map(lambda x: self.zip_input_with_agg(x)) \
            .map(lambda x: self.build_output_message(x)) \
            .publish()  # This is required for multiple subscriptions

        # Main subscription
        rx.subscribe(lambda x: self.stream.push(str(x)))

        # Middleware
        for mw in self.middleware:
            rx.subscribe(mw)

        # Connect with observers
        rx.connect()