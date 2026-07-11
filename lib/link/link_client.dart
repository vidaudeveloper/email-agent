import '../models/device.dart';
import '../models/link_events.dart';

/// Transport to Cloud Link Gateway (or a local mock).
abstract class LinkClient {
  Stream<LinkEvent> get events;

  Future<void> connect({required String accessToken});

  Future<void> disconnect();

  Future<List<Device>> listDevices();

  Future<void> sendChat({required String deviceId, required String text});

  Future<void> pullHistory({required String deviceId, int limit = 50});
}
