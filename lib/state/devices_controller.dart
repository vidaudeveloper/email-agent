import 'package:flutter/foundation.dart';

import '../core/config.dart';
import '../data/local_db.dart';
import '../link/link_client.dart';
import '../models/device.dart';
import '../models/link_events.dart';

class DevicesController extends ChangeNotifier {
  DevicesController({
    required LinkClient linkClient,
    required LocalDb localDb,
    required AppConfig config,
  })  : _linkClient = linkClient,
        _localDb = localDb,
        _config = config;

  final LinkClient _linkClient;
  final LocalDb _localDb;
  final AppConfig _config;

  List<Device> devices = [];
  bool loading = false;
  String? error;

  Future<void> refresh() async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      final remote = await _linkClient.listDevices();
      // Always trust live list in remote mode — never keep stale Mock rows.
      if (_config.linkMode == LinkMode.remote) {
        await _localDb.replaceDevices(remote);
        devices = remote;
      } else {
        for (final d in remote) {
          await _localDb.upsertDevice(d);
        }
        devices = remote.isNotEmpty ? remote : await _localDb.listDevices();
      }
      if (devices.isEmpty) {
        error = _config.linkMode == LinkMode.remote
            ? '暂无在线电脑。请确认桌面已 vidau gateway start，且 Mobile Link 已连接。'
            : null;
      }
    } catch (e) {
      error = e.toString();
      if (_config.linkMode == LinkMode.remote) {
        devices = [];
      } else {
        devices = await _localDb.listDevices();
      }
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  void applyDeviceStatus(LinkEvent event) {
    if (event.type != LinkEventType.deviceStatus || event.deviceId == null) {
      return;
    }
    final online = (event.status ?? '').toLowerCase() == 'online';
    final idx = devices.indexWhere((d) => d.deviceId == event.deviceId);
    if (idx < 0 && online) {
      devices = [
        ...devices,
        Device(
          deviceId: event.deviceId!,
          name: event.deviceId!,
          status: DeviceStatus.online,
        ),
      ];
    } else if (idx >= 0) {
      devices = [
        for (var i = 0; i < devices.length; i++)
          if (i == idx)
            devices[i].copyWith(
              status: online ? DeviceStatus.online : DeviceStatus.offline,
            )
          else
            devices[i],
      ];
    }
    notifyListeners();
  }
}
