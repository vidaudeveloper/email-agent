enum LinkMode { mock, remote }

/// App-wide config.
///
/// Override at run time for a physical phone (simulator can keep 127.0.0.1):
/// `flutter run --dart-define=GATEWAY_HOST=192.168.x.x`
class AppConfig {
  const AppConfig({
    required this.linkMode,
    required this.gatewayHttpBaseUrl,
    required this.gatewayWsUrl,
  });

  final LinkMode linkMode;
  final String gatewayHttpBaseUrl;
  final String gatewayWsUrl;

  static AppConfig get current {
    const modeName = String.fromEnvironment('LINK_MODE', defaultValue: 'remote');
    const host = String.fromEnvironment('GATEWAY_HOST', defaultValue: '127.0.0.1');
    const port = String.fromEnvironment('GATEWAY_PORT', defaultValue: '8787');
    final mode = modeName == 'mock' ? LinkMode.mock : LinkMode.remote;
    return AppConfig(
      linkMode: mode,
      gatewayHttpBaseUrl: 'http://$host:$port',
      gatewayWsUrl: 'ws://$host:$port/ws',
    );
  }
}
