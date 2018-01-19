from __future__ import print_function

import json
from copy import copy
from datetime import datetime

from google.protobuf.descriptor import FieldDescriptor

from dropsonde import TYPE_CALLABLE_MAP
from dropsonde import protobuf_to_dict
from dropsonde.envelope_pb2 import Envelope


# BEGIN SHIM
# this is a shim that fixes an issue in the protobuf-to-dict library

type_callable_map = copy(TYPE_CALLABLE_MAP)
type_callable_map[FieldDescriptor.TYPE_BYTES] = str
_handle_pb_message = type_callable_map[FieldDescriptor.TYPE_MESSAGE]


def handle_pb_message(v, **kwargs):
    class_name = type(v).__name__
    if "ScalarMapContainer" == class_name:
        return dict(v.items())
    if 'unicode' == class_name:
        return v
    return _handle_pb_message(v, **kwargs)


type_callable_map[FieldDescriptor.TYPE_MESSAGE] = handle_pb_message
protobuf_to_dict_kwargs = dict(
    type_callable_map=type_callable_map,
    use_enum_labels=True
)


# END SHIM


def parse_envelope_protobuf(pbstr):
    """Parses a protocol buffers string into a dictionary representing a
    Dropsonde Envelope protobuf message type

    Args:
        pbstr (basestring): protocol buffers string

    Returns:
        dict
    """
    env = Envelope()
    env.ParseFromString(pbstr)
    env = protobuf_to_dict(env, **protobuf_to_dict_kwargs)
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


def get_uuid_string(**x):
    """This method parses a UUID protobuf message type from its component
    'high' and 'low' longs into a standard formatted UUID string

    Args:
        x (dict): containing keys, 'low' and 'high' corresponding to the UUID
            protobuf message type

    Returns:
        str: UUID formatted string
    """
    if 'low' not in x or 'high' not in x:
        return None

    # convert components to hex strings and strip off '0x'
    l = hex(x['low'])[2:-1]
    h = hex(x['high'])[2:-1]

    # ensure we have leading 0 bytes set
    l = ''.join(['0' * (16 - len(l)), l])
    h = ''.join(['0' * (16 - len(h)), h])

    # split/reverse/join little endian bytes
    x = ''.join([
        ''.join([l[i:i+2] for i in xrange(0, len(l), 2)][::-1]),
        ''.join([h[i:i+2] for i in xrange(0, len(h), 2)][::-1]),
    ])

    # create uuid formatted string
    return '-'.join([x[:8], x[8:12], x[12:16], x[16:20], x[20:]])


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
            str(self.message)
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
            return self.get('logMessage', {}).get('message', '')
        elif self.is_event_type('ValueMetric'):
            return json.dumps(self['valueMetric'])
        elif self.is_event_type('ContainerMetric'):
            return json.dumps(self['containerMetric'])
        elif self.is_event_type('CounterEvent'):
            return json.dumps(self['counterEvent'])
        else:
            return json.dumps(self)

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
            pbstr (basestring)

        Returns:
            DopplerEnvelope|None: if a falsy value is passed in, None is
            returned, else a DopplerEnvelope is returned.
        """
        if not pbstr:
            return None
        if isinstance(pbstr, basestring):
            pbstr = parse_envelope_protobuf(pbstr)
        return DopplerEnvelope(pbstr)
