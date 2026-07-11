import 'package:flutter_test/flutter_test.dart';
import 'package:vidau_mobile/link/mock_link_client.dart';
import 'package:vidau_mobile/models/link_events.dart';

void main() {
  test('sendChat emits user then done', () async {
    final client = MockLinkClient();
    await client.connect(accessToken: 'test');

    final done = client.events.firstWhere(
      (e) => e.type == LinkEventType.chatDone,
    );
    await client.sendChat(deviceId: 'macbook-pro-01', text: 'hello');
    final event = await done.timeout(const Duration(seconds: 3));
    expect(event.status, 'success');

    final devices = await client.listDevices();
    expect(devices, isNotEmpty);
    expect(devices.first.isOnline, isTrue);

    await client.dispose();
  });
}
