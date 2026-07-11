import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../core/config.dart';
import '../data/auth_store.dart';
import '../data/local_db.dart';
import '../link/link_client.dart';

class AuthController extends ChangeNotifier {
  AuthController({
    required AuthStore authStore,
    required LinkClient linkClient,
    required AppConfig config,
    required LocalDb localDb,
    http.Client? httpClient,
  })  : _authStore = authStore,
        _linkClient = linkClient,
        _config = config,
        _localDb = localDb,
        _http = httpClient ?? http.Client();

  final AuthStore _authStore;
  final LinkClient _linkClient;
  final AppConfig _config;
  final LocalDb _localDb;
  final http.Client _http;

  AuthSession? session;
  bool loading = true;
  String? error;

  Future<void> bootstrap() async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      // Drop stale Mock sessions when running remote — force a clean login.
      if (_config.linkMode == LinkMode.remote) {
        final existing = await _authStore.read();
        if (existing?.accessToken == 'demo-token') {
          await _authStore.clear();
          await _localDb.clearDevices();
          session = null;
          return;
        }
      }
      session = await _authStore.read();
      if (session != null) {
        await _linkClient.connect(accessToken: session!.accessToken);
      }
    } catch (e) {
      error = e.toString();
      session = null;
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  /// Demo login — hits Gateway `/auth/demo` in remote mode, or local token in mock.
  Future<void> signInDemo() async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      late final AuthSession demo;
      if (_config.linkMode == LinkMode.remote) {
        final uri = Uri.parse('${_config.gatewayHttpBaseUrl}/auth/demo');
        final res = await _http.post(
          uri,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'user_id': 'demo-user'}),
        );
        if (res.statusCode < 200 || res.statusCode >= 300) {
          throw StateError(
            '无法连接 Link Gateway (${res.statusCode}). '
            '请先在电脑运行: cd mobile_agent_service && ./scripts/run.sh\n'
            '${res.body}',
          );
        }
        final body = jsonDecode(res.body) as Map<String, dynamic>;
        demo = AuthSession(
          userId: body['user_id'] as String? ?? 'demo-user',
          accessToken: body['access_token'] as String,
        );
        await _localDb.clearDevices();
      } else {
        demo = const AuthSession(
          userId: 'demo-user',
          accessToken: 'demo-token',
        );
      }
      await _authStore.save(demo);
      await _linkClient.connect(accessToken: demo.accessToken);
      session = demo;
    } catch (e) {
      error = e.toString();
      session = null;
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> signOut() async {
    await _linkClient.disconnect();
    await _authStore.clear();
    if (_config.linkMode == LinkMode.remote) {
      await _localDb.clearDevices();
    }
    session = null;
    notifyListeners();
  }
}
