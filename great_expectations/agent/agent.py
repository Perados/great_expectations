import os
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Dict, Optional

from pydantic.dataclasses import dataclass
from pydantic import AmqpDsn
from great_expectations import get_context
from great_expectations.agent.event_handler import EventHandler
from great_expectations.agent.message_service.rabbit_mq_client import (
    RabbitMQClient,
    ClientError,
)
from great_expectations.agent.message_service.subscriber import (
    Subscriber,
    OnMessageCallback,
    SubscriberError,
    RequeueMessageError,
)
from great_expectations.agent.models import Event
from great_expectations.data_context import CloudDataContext


HandlerMap = Dict[str, OnMessageCallback]


@dataclass(frozen=True)
class GXAgentConfig:
    """GXAgent configuration.
    Attributes:
        organization_id: GX Cloud organization identifier
        broker_url: address of broker service
    """

    organization_id: str
    broker_url: AmqpDsn


class GXAgent:
    """
    Run GX in any environment from GX Cloud.

    To start the agent, install Python and great_expectations and run `gx-agent`.
    The agent loads a DataContext configuration from GX Cloud, and listens for
    user events triggered from the UI.
    """

    def __init__(self):
        print("Initializing GX-Agent")
        self._config = self._get_config_from_env()
        print("Loading a DataContext - this might take a moment.")
        self._context: CloudDataContext = get_context(cloud_mode=True)
        print("DataContext is ready.")

        # Create a thread pool with a single worker, so we can run long-lived
        # GX processes and maintain our connection to the broker. Note that
        # the CloudDataContext cached here is used by the worker, therefore
        # it isn't safe to increase the number of workers.
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._current_task = None

    def run(self) -> None:
        """Open a connection to GX Cloud."""

        print("Opening connection to GX Cloud")
        self._listen()
        print("Connection to GX Cloud has been closed.")

    def _listen(self) -> None:
        """Manage connection lifecycle."""
        subscriber = None
        try:
            client = RabbitMQClient(url=self._config.broker_url)
            subscriber = Subscriber(client=client)
            print("GX-Agent is ready.")
            # Open a blocking connection until encountering a shutdown event
            subscriber.consume(
                queue=self._config.organization_id,
                on_message=self._handle_event_as_thread,
            )
        except KeyboardInterrupt:
            print("Received request to shutdown.")
        except (SubscriberError, ClientError) as e:
            print("Connection to GX Cloud has encountered an error.")
            print("Please restart the agent and try your action again.")
            print(e)
        finally:
            self._close_subscriber(subscriber)

    def _handle_event_as_thread(self, event: Event, correlation_id: str) -> None:
        """Schedule _handle_event to run in a thread.

        Callback passed to Subscriber.consume which forwards events to
        the EventHandler for processing.

        Args:
            event: pydantic model representing an event
            correlation_id: stable identifier for an event across its lifecycle
        Raises:
            RequeueMessageError when the worker is busy
        """

        if self._can_accept_new_task() is not True:
            # signal to Subscriber that we can't process this message right now
            raise RequeueMessageError
        self._current_task = self._executor.submit(
            self._handle_event, event=event, correlation_id=correlation_id
        )

    def _handle_event(self, event: Event, correlation_id: str) -> None:
        """Pass events to EventHandler.

        Callback passed to Subscriber.consume which forwards events to
        the EventHandler for processing.

        Args:
            event: pydantic model representing an event
            correlation_id: stable identifier for an event across its lifecycle
        """
        # TODO lakitu-139: record job as started

        handler = EventHandler(context=self._context)
        handler.handle_event(event=event, correlation_id=correlation_id)

        # TODO lakitu-139: record job as complete
        return

    def _can_accept_new_task(self) -> bool:
        return self._current_task is None or self._current_task.done()

    def _close_subscriber(self, subscriber: Optional[Subscriber]) -> None:
        """Ensure the subscriber has been closed."""
        if subscriber is None:
            return  # nothing to close
        try:
            subscriber.close()
        except SubscriberError as e:
            print("Subscriber encountered an error while closing:")
            print(e)

    @classmethod
    def _get_config_from_env(cls) -> GXAgentConfig:
        """Construct GXAgentConfig from available environment variables"""
        url = os.environ.get("BROKER_URL", None)
        if url is None:
            raise GXAgentError("Missing required environment variable: BROKER_URL")
        org_id = os.environ.get("GE_CLOUD_ORGANIZATION_ID", None)
        if org_id is None:
            raise GXAgentError(
                "Missing required environment variable: GE_CLOUD_ORGANIZATION_ID"
            )
        return GXAgentConfig(organization_id=org_id, broker_url=url)


class GXAgentError(Exception):
    ...
