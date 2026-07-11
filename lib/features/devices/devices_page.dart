import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../../core/config.dart';
import '../../link/link_client.dart';
import '../../models/device.dart';
import '../../models/link_events.dart';
import '../../state/auth_controller.dart';
import '../../state/devices_controller.dart';
import '../../widgets/link_mode_banner.dart';
import 'dart:async';

class DevicesPage extends StatefulWidget {
  const DevicesPage({super.key});

  @override
  State<DevicesPage> createState() => _DevicesPageState();
}

class _DevicesPageState extends State<DevicesPage> {
  StreamSubscription<LinkEvent>? _sub;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final devices = context.read<DevicesController>();
      final link = context.read<LinkClient>();
      devices.refresh();
      _sub = link.events.listen(devices.applyDeviceStatus);
    });
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final devices = context.watch<DevicesController>();
    final auth = context.watch<AuthController>();
    final config = context.watch<AppConfig>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('我的电脑'),
        bottom: const PreferredSize(
          preferredSize: Size.fromHeight(28),
          child: LinkModeBanner(),
        ),
        actions: [
          IconButton(
            tooltip: '刷新',
            onPressed: devices.loading ? null : () => devices.refresh(),
            icon: const Icon(Icons.refresh),
          ),
          IconButton(
            tooltip: '退出',
            onPressed: () async {
              await auth.signOut();
              if (context.mounted) context.go('/login');
            },
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: devices.refresh,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (devices.error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(
                  devices.error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            if (devices.loading && devices.devices.isEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 48),
                child: Center(child: CircularProgressIndicator()),
              ),
            ...devices.devices.map((d) => _DeviceTile(device: d)),
            if (!devices.loading && devices.devices.isEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 48),
                child: Text(
                  config.linkMode == LinkMode.remote
                      ? '暂无在线电脑。\n1) 服务端 ./scripts/run.sh\n'
                          '2) 桌面 vidau gateway start\n'
                          '3) 下拉刷新'
                      : '暂无设备。',
                  textAlign: TextAlign.center,
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _DeviceTile extends StatelessWidget {
  const _DeviceTile({required this.device});

  final Device device;

  @override
  Widget build(BuildContext context) {
    final online = device.isOnline;
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
      leading: Icon(
        Icons.computer,
        color: online
            ? Theme.of(context).colorScheme.primary
            : Theme.of(context).colorScheme.outline,
      ),
      title: Text(device.name),
      subtitle: Text(
        online ? '在线 · ${device.deviceId}' : '离线 · ${device.deviceId}',
      ),
      trailing: online ? const Icon(Icons.chevron_right) : null,
      onTap: online
          ? () => context.push('/chat/${device.deviceId}', extra: device.name)
          : null,
    );
  }
}
