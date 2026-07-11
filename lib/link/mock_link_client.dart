import 'dart:async';

import 'package:uuid/uuid.dart';

import '../models/device.dart';
import '../models/link_events.dart';
import 'link_client.dart';

/// Local fake desktop: no network. Used until link-gateway exists.
class MockLinkClient implements LinkClient {
  MockLinkClient({Uuid? uuid}) : _uuid = uuid ?? const Uuid();

  final Uuid _uuid;
  final _controller = StreamController<LinkEvent>.broadcast();
  var _connected = false;

  static const demoDevice = Device(
    deviceId: 'macbook-pro-01',
    name: 'Kean-MacBook-Pro',
    status: DeviceStatus.online,
  );

  @override
  Stream<LinkEvent> get events => _controller.stream;

  @override
  Future<void> connect({required String accessToken}) async {
    _connected = true;
  }

  @override
  Future<void> disconnect() async {
    _connected = false;
  }

  @override
  Future<List<Device>> listDevices() async {
    _ensureConnected();
    return const [demoDevice];
  }

  @override
  Future<void> sendChat({required String deviceId, required String text}) async {
    _ensureConnected();
    final msgId = _uuid.v4();
    final sessionId = 'mock-session-$deviceId';

    _controller.add(
      LinkEvent(
        type: LinkEventType.chatUser,
        msgId: msgId,
        deviceId: deviceId,
        sessionId: sessionId,
        text: text,
        ts: DateTime.now(),
      ),
    );

    await Future<void>.delayed(const Duration(milliseconds: 250));
    _controller.add(
      LinkEvent(
        type: LinkEventType.chatProgress,
        msgId: msgId,
        deviceId: deviceId,
        sessionId: sessionId,
        text: '桌面 Agent 正在执行…',
        ts: DateTime.now(),
      ),
    );

    await Future<void>.delayed(const Duration(milliseconds: 400));
    _controller.add(
      LinkEvent(
        type: LinkEventType.chatAssistant,
        msgId: '$msgId-assistant',
        deviceId: deviceId,
        sessionId: sessionId,
        text: '（Mock）已收到指令「$text」，桌面端将在接入 Gateway 后真实执行。',
        ts: DateTime.now(),
      ),
    );

    _controller.add(
      LinkEvent(
        type: LinkEventType.chatDone,
        msgId: msgId,
        deviceId: deviceId,
        sessionId: sessionId,
        status: 'success',
        ts: DateTime.now(),
      ),
    );
  }

  @override
  Future<void> pullHistory({required String deviceId, int limit = 50}) async {
    _ensureConnected();
    _controller.add(
      LinkEvent(
        type: LinkEventType.historySnapshot,
        deviceId: deviceId,
        messages: const [],
        ts: DateTime.now(),
      ),
    );
  }

  void _ensureConnected() {
    if (!_connected) {
      throw StateError('MockLinkClient is not connected');
    }
  }

  Future<void> dispose() async {
    await _controller.close();
  }
}
