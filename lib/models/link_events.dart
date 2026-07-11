enum LinkEventType {
  registerDevice,
  ping,
  pong,
  deviceStatus,
  chatSend,
  chatUser,
  chatAssistant,
  chatProgress,
  chatDone,
  chatError,
  historyPull,
  historySnapshot,
}

class LinkEvent {
  const LinkEvent({
    required this.type,
    this.msgId,
    this.sessionId,
    this.deviceId,
    this.userId,
    this.ts,
    this.text,
    this.status,
    this.messages,
  });

  final LinkEventType type;
  final String? msgId;
  final String? sessionId;
  final String? deviceId;
  final String? userId;
  final DateTime? ts;
  final String? text;
  final String? status;
  final List<Map<String, dynamic>>? messages;

  static LinkEvent chatSend({
    required String msgId,
    required String deviceId,
    required String text,
    String? sessionId,
    String? userId,
  }) {
    return LinkEvent(
      type: LinkEventType.chatSend,
      msgId: msgId,
      deviceId: deviceId,
      text: text,
      sessionId: sessionId,
      userId: userId,
      ts: DateTime.now(),
    );
  }

  static LinkEventType? typeFromWire(String? raw) {
    switch (raw) {
      case 'register_device':
        return LinkEventType.registerDevice;
      case 'ping':
        return LinkEventType.ping;
      case 'pong':
        return LinkEventType.pong;
      case 'device_status':
        return LinkEventType.deviceStatus;
      case 'chat.send':
        return LinkEventType.chatSend;
      case 'chat.user':
        return LinkEventType.chatUser;
      case 'chat.assistant':
        return LinkEventType.chatAssistant;
      case 'chat.progress':
        return LinkEventType.chatProgress;
      case 'chat.done':
        return LinkEventType.chatDone;
      case 'chat.error':
        return LinkEventType.chatError;
      case 'history.pull':
        return LinkEventType.historyPull;
      case 'history.snapshot':
        return LinkEventType.historySnapshot;
      default:
        return null;
    }
  }

  String get wireType {
    switch (type) {
      case LinkEventType.registerDevice:
        return 'register_device';
      case LinkEventType.ping:
        return 'ping';
      case LinkEventType.pong:
        return 'pong';
      case LinkEventType.deviceStatus:
        return 'device_status';
      case LinkEventType.chatSend:
        return 'chat.send';
      case LinkEventType.chatUser:
        return 'chat.user';
      case LinkEventType.chatAssistant:
        return 'chat.assistant';
      case LinkEventType.chatProgress:
        return 'chat.progress';
      case LinkEventType.chatDone:
        return 'chat.done';
      case LinkEventType.chatError:
        return 'chat.error';
      case LinkEventType.historyPull:
        return 'history.pull';
      case LinkEventType.historySnapshot:
        return 'history.snapshot';
    }
  }

  Map<String, dynamic> toJson() {
    return {
      'type': wireType,
      if (msgId != null) 'msg_id': msgId,
      if (sessionId != null) 'session_id': sessionId,
      if (deviceId != null) 'device_id': deviceId,
      if (deviceId != null) 'target_device': deviceId,
      if (userId != null) 'user_id': userId,
      if (ts != null) 'ts': ts!.toIso8601String(),
      if (text != null) 'text': text,
      if (text != null) 'content': text,
      if (status != null) 'status': status,
      if (messages != null) 'messages': messages,
    };
  }

  factory LinkEvent.fromJson(Map<String, dynamic> json) {
    final type = typeFromWire(json['type'] as String?);
    if (type == null) {
      throw FormatException('Unknown link event type: ${json['type']}');
    }
    final text = json['text'] as String? ?? json['content'] as String?;
    final deviceId =
        json['device_id'] as String? ?? json['target_device'] as String?;
    final rawMessages = json['messages'];
    return LinkEvent(
      type: type,
      msgId: json['msg_id'] as String? ?? json['cmd_id'] as String?,
      sessionId: json['session_id'] as String?,
      deviceId: deviceId,
      userId: json['user_id'] as String?,
      ts: DateTime.tryParse(json['ts'] as String? ?? ''),
      text: text,
      status: json['status'] as String?,
      messages: rawMessages is List
          ? rawMessages.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList()
          : null,
    );
  }
}
