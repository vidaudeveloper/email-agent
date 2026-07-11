enum ChatRole { user, assistant, progress, system }

class ChatMessage {
  const ChatMessage({
    required this.msgId,
    required this.deviceId,
    required this.role,
    required this.text,
    required this.createdAt,
    this.sessionId,
  });

  final String msgId;
  final String deviceId;
  final String? sessionId;
  final ChatRole role;
  final String text;
  final DateTime createdAt;

  Map<String, dynamic> toMap() => {
        'msg_id': msgId,
        'device_id': deviceId,
        'session_id': sessionId,
        'role': role.name,
        'text': text,
        'created_at': createdAt.toIso8601String(),
      };

  factory ChatMessage.fromMap(Map<String, dynamic> map) {
    return ChatMessage(
      msgId: map['msg_id'] as String,
      deviceId: map['device_id'] as String,
      sessionId: map['session_id'] as String?,
      role: ChatRole.values.firstWhere(
        (r) => r.name == map['role'],
        orElse: () => ChatRole.system,
      ),
      text: map['text'] as String? ?? '',
      createdAt: DateTime.tryParse(map['created_at'] as String? ?? '') ??
          DateTime.now(),
    );
  }
}
