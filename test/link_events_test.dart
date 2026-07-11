import 'package:flutter_test/flutter_test.dart';
import 'package:vidau_mobile/models/link_events.dart';

void main() {
  test('chat.send roundtrip', () {
    final event = LinkEvent.chatSend(
      msgId: 'm1',
      deviceId: 'mac-1',
      text: '打开 Finder',
    );
    final decoded = LinkEvent.fromJson(event.toJson());
    expect(decoded.type, LinkEventType.chatSend);
    expect(decoded.text, '打开 Finder');
    expect(decoded.deviceId, 'mac-1');
    expect(decoded.msgId, 'm1');
  });

  test('wire type mapping for progress and done', () {
    expect(
      LinkEvent.typeFromWire('chat.progress'),
      LinkEventType.chatProgress,
    );
    expect(LinkEvent.typeFromWire('chat.done'), LinkEventType.chatDone);
  });
}
