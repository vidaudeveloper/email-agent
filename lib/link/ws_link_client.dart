import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:uuid/uuid.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../core/config.dart';
import '../models/device.dart';
import '../models/link_events.dart';
import 'link_client.dart';

/// Real Gateway client. Enable with [LinkMode.remote] after link-gateway exists.
class WsLinkClient implements LinkClient {
  WsLinkClient({
    required this.config,
    http.Client? httpClient,
    Uuid? uuid,
  })  : _http = httpClient ?? http.Client(),
        _uuid = uuid ?? const Uuid();

  final AppConfig config;
  final http.Client _http;
  final Uuid _uuid;

  final _controller = StreamController<LinkEvent>.broadcast();
  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _sub;
  String? _token;

  @override
  Stream<LinkEvent> get events => _controller.stream;

  @override
  Future<void> connect({required String accessToken}) async {
    await disconnect();
    _token = accessToken;
    final uri = Uri.parse(config.gatewayWsUrl).replace(
      queryParameters: {
        'token': accessToken,
        'role': 'mobile',
      },
    );
    _channel = WebSocketChannel.connect(uri);
    _sub = _channel!.stream.listen(
      (raw) {
        try {
          final map = jsonDecode(raw as String) as Map<String, dynamic>;
          _controller.add(LinkEvent.fromJson(map));
        } catch (e, st) {
          _controller.addError(e, st);
        }
      },
      onError: _controller.addError,
      onDone: () {},
    );
  }

  @override
  Future<void> disconnect() async {
    await _sub?.cancel();
    _sub = null;
    await _channel?.sink.close();
    _channel = null;
  }

  @override
  Future<List<Device>> listDevices() async {
    final token = _token;
    if (token == null) {
      throw StateError('WsLinkClient is not connected');
    }
    final uri = Uri.parse('${config.gatewayHttpBaseUrl}/devices');
    final res = await _http.get(
      uri,
      headers: {'Authorization': 'Bearer $token'},
    );
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw StateError('GET /devices failed: ${res.statusCode} ${res.body}');
    }
    final decoded = jsonDecode(res.body);
    final list = decoded is List ? decoded : (decoded['devices'] as List? ?? []);
    return list
        .whereType<Map>()
        .map((e) => Device.fromJson(Map<String, dynamic>.from(e)))
        .toList();
  }

  @override
  Future<void> sendChat({required String deviceId, required String text}) async {
    final channel = _channel;
    if (channel == null) {
      throw StateError('WsLinkClient is not connected');
    }
    final event = LinkEvent.chatSend(
      msgId: _uuid.v4(),
      deviceId: deviceId,
      text: text,
    );
    channel.sink.add(jsonEncode(event.toJson()));
  }

  @override
  Future<void> pullHistory({required String deviceId, int limit = 50}) async {
    final channel = _channel;
    if (channel == null) {
      throw StateError('WsLinkClient is not connected');
    }
    channel.sink.add(
      jsonEncode({
        'type': 'history.pull',
        'device_id': deviceId,
        'limit': limit,
        'ts': DateTime.now().toIso8601String(),
      }),
    );
  }
}
