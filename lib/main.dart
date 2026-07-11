import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'app.dart';
import 'core/config.dart';
import 'data/auth_store.dart';
import 'data/local_db.dart';
import 'link/link_client.dart';
import 'link/mock_link_client.dart';
import 'link/ws_link_client.dart';
import 'state/auth_controller.dart';
import 'state/devices_controller.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final config = AppConfig.current;
  final authStore = AuthStore();
  final localDb = await LocalDb.open();
  final linkClient = _createLinkClient(config);

  final authController = AuthController(
    authStore: authStore,
    linkClient: linkClient,
    config: config,
    localDb: localDb,
  );
  final devicesController = DevicesController(
    linkClient: linkClient,
    localDb: localDb,
    config: config,
  );

  debugPrint(
    'Vidau Mobile starting linkMode=${config.linkMode.name} '
    'client=${linkClient.runtimeType} http=${config.gatewayHttpBaseUrl}',
  );

  await authController.bootstrap();
  final router = buildRouter(authController);

  runApp(
    MultiProvider(
      providers: [
        Provider<AppConfig>.value(value: config),
        Provider<LinkClient>.value(value: linkClient),
        Provider<LocalDb>.value(value: localDb),
        Provider<AuthStore>.value(value: authStore),
        ChangeNotifierProvider<AuthController>.value(value: authController),
        ChangeNotifierProvider<DevicesController>.value(value: devicesController),
      ],
      child: VidauApp(router: router),
    ),
  );
}

LinkClient _createLinkClient(AppConfig config) {
  switch (config.linkMode) {
    case LinkMode.mock:
      return MockLinkClient();
    case LinkMode.remote:
      return WsLinkClient(config: config);
  }
}
