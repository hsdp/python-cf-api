from __future__ import print_function
import six
import json
from copy import copy
from datetime import datetime
from google.protobuf.descriptor import FieldDescriptor
from dropsonde.pb.envelope_pb2 import Envelope
from .pb2dict import TYPE_CALLABLE_MAP, protobuf_to_dict


def _json_encoder(o):
    if isinstance(o, six.binary_type):
        return o.decode('utf-8')
    elif isinstance(o, six.string_types):
        return str(o)
    else:
        return o.__dict__


def parse_envelope_protobuf(pbstr):
    """Parses a protocol buffers string into a dictionary representing a
    Dropsonde Envelope protobuf message type

    Args:
        pbstr (six.binary_type): protocol buffers string

    Returns:
        dict
    """
    env = Envelope()
    env.ParseFromString(pbstr)
    env = protobuf_to_dict(env)
    return env


def format_unixnano(unixnano):
    """Formats an integer unix timestamp from nanoseconds to a user readable
    string

    Args:
        unixnano (int): integer unix timestamp in nanoseconds
    Returns:
        formatted_time (str)
    """
    return datetime.fromtimestamp(int(unixnano / 1e6) / 1000.0)\
        .strftime('%Y-%m-%d %H:%M:%S.%f')


def render_log_http_start_stop(m):
    """Formats an HttpStartStop protobuf event type

    Args:
        m (DopplerEnvelope): envelope object

    Returns:
        str: string message that may be printed
    """
    if not isinstance(m, DopplerEnvelope):
        m = DopplerEnvelope(m)
    hss = m['httpStartStop']
    return ' '.join([
        format_unixnano(m['timestamp']),
        ': ',
        str((hss['stopTimestamp'] - hss['startTimestamp']) / float(1e6)),
        'ms',
        format_unixnano(hss['startTimestamp']),
        str(m.app_id),
        hss['peerType'],
        hss['method'],
        str(hss.get('uri', None))
    ])


class DopplerEnvelope(dict):
    """Utility class for parsing Doppler Envelope protocol buffers messages
    and accessing their members
    """
    def __init__(self, pbstr):
        super(DopplerEnvelope, self).__init__(**pbstr)
        self['eventType'] = Envelope.EventType.Name(self['eventType'])

    def __getattr__(self, item):
        return self.get(item, None)

    def __str__(self):
        """Builds a string log message from this class
        """
        return ''.join([
            '[ ',
            ' - '.join([
                str(self['eventType']),
                str(self['origin']),
                str(self['deployment']),
                format_unixnano(self['timestamp'])]),
            ' ]:  ',
            self.message
        ])

    def __repr__(self):
        return self.__str__()

    def is_event_type(self, *event_type):
        """Checks if the event type is one of the passed in arguments

        Args:
            event_type (tuple[str]): HttpStartStop, LogMessage, CounterEvent,
                ContainerEvent, ValueMetric

        Returns:
            bool
        """
        return self['eventType'] in event_type

    @property
    def message(self):
        """String message representing this envelope customized for several
        event types
        """
        if self.is_event_type('HttpStartStop'):
            return str(render_log_http_start_stop(self))
        elif self.is_event_type('LogMessage'):
            msg = self.get('logMessage', {}).get('message', '')
            try:
                return msg.decode('utf-8')
            except:
                return str(msg)
        elif self.is_event_type('ValueMetric'):
            return json.dumps(self['valueMetric'])
        elif self.is_event_type('ContainerMetric'):
            return json.dumps(self['containerMetric'])
        elif self.is_event_type('CounterEvent'):
            return json.dumps(self['counterEvent'])
        else:
            return json.dumps(self, default=_json_encoder)

    @property
    def request_id(self):
        """Fetches the request UUID converting it from the UUID envelope
        message type. Currently this is only applicable to the HttpStartStop
        event type
        """
        if self.is_event_type('HttpStartStop'):
            return get_uuid_string(
                    **self['httpStartStop'].get('requestId', {}))
        else:
            return None

    @property
    def app_id(self):
        """Fetches the application UUID converting it from the UUID envelope
        message type. Currently this is only applicable to the HttpStartStop
        and LogMessage event types.
        """
        if self.is_event_type('HttpStartStop'):
            return get_uuid_string(
                    **self['httpStartStop'].get('applicationId', {}))
        else:
            return self.get('logMessage', {}).get('app_id', None)

    @staticmethod
    def wrap(pbstr):
        """Parses a protobuf string into an Envelope dictionary

        Args:
            pbstr (str)

        Returns:
            DopplerEnvelope|None: if a falsy value is passed in, None is
            returned, else a DopplerEnvelope is returned.
        """
        if not pbstr:
            return None
        if isinstance(pbstr, (six.text_type, six.binary_type)):
            pbstr = parse_envelope_protobuf(pbstr)
        return DopplerEnvelope(pbstr)
