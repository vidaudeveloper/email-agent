import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';

import '../data/local_db.dart';
import '../link/link_client.dart';
import '../models/chat_message.dart';
import '../models/link_events.dart';

class ChatController extends ChangeNotifier {
  ChatController({
    required this.deviceId,
    required LinkClient linkClient,
    required LocalDb localDb,
    Uuid? uuid,
  })  : _linkClient = linkClient,
        _localDb = localDb,
        _uuid = uuid ?? const Uuid();

  final String deviceId;
  final LinkClient _linkClient;
  final LocalDb _localDb;
  final Uuid _uuid;

  final List<ChatMessage> messages = [];
  bool sending = false;
  String? error;
  StreamSubscription<LinkEvent>? _sub;

  Future<void> start() async {
    messages
      ..clear()
      ..addAll(await _localDb.messagesForDevice(deviceId));
    notifyListeners();

    _sub = _linkClient.events.listen(_onEvent, onError: (Object e) {
      error = e.toString();
      notifyListeners();
    });

    try {
      await _linkClient.pullHistory(deviceId: deviceId);
    } catch (_) {
      // Optional on mock / offline.
    }
  }

  Future<void> send(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || sending) return;
    sending = true;
    error = null;
    notifyListeners();
    try {
      // Optimistic local bubble; server/mock will also emit chat.user.
      final optimistic = ChatMessage(
        msgId: 'local-${_uuid.v4()}',
        deviceId: deviceId,
        role: ChatRole.user,
        text: trimmed,
        createdAt: DateTime.now(),
      );
      await _append(optimistic, persist: true);
      await _linkClient.sendChat(deviceId: deviceId, text: trimmed);
    } catch (e) {
      error = e.toString();
    } finally {
      sending = false;
      notifyListeners();
    }
  }

  void _onEvent(LinkEvent event) {
    // chat.error may omit device_id (e.g. offline) — still surface it.
    if (event.type == LinkEventType.chatError) {
      if (event.deviceId != null && event.deviceId != deviceId) return;
      error = event.text ?? event.status ?? 'chat.error';
      notifyListeners();
      return;
    }

    if (event.deviceId != null && event.deviceId != deviceId) return;

    switch (event.type) {
      case LinkEventType.chatUser:
        _upsertFromEvent(event, ChatRole.user);
      case LinkEventType.chatAssistant:
        _upsertFromEvent(event, ChatRole.assistant);
      case LinkEventType.chatProgress:
        _upsertFromEvent(event, ChatRole.progress);
      case LinkEventType.historySnapshot:
        break;
      default:
        break;
    }
  }

  Future<void> _upsertFromEvent(LinkEvent event, ChatRole role) async {
    final text = event.text;
    if (text == null || text.isEmpty) return;
    final msg = ChatMessage(
      msgId: event.msgId ?? _uuid.v4(),
      deviceId: deviceId,
      sessionId: event.sessionId,
      role: role,
      text: text,
      createdAt: event.ts ?? DateTime.now(),
    );
    // Avoid duplicating optimistic local user bubble with same text near-term.
    if (role == ChatRole.user &&
        messages.isNotEmpty &&
        messages.last.role == ChatRole.user &&
        messages.last.text == text &&
        messages.last.msgId.startsWith('local-')) {
      messages.removeLast();
    }
    await _append(msg, persist: role != ChatRole.progress);
  }

  Future<void> _append(ChatMessage msg, {required bool persist}) async {
    final idx = messages.indexWhere((m) => m.msgId == msg.msgId);
    if (idx >= 0) {
      messages[idx] = msg;
    } else {
      messages.add(msg);
    }
    if (persist) {
      await _localDb.insertMessage(msg);
    }
    notifyListeners();
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}
