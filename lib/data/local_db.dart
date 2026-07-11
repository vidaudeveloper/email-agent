import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';

import '../models/chat_message.dart';
import '../models/device.dart';

class LocalDb {
  LocalDb._(this._db);

  final Database _db;

  static Future<LocalDb> open() async {
    final dbPath = await getDatabasesPath();
    final path = p.join(dbPath, 'vidau_mobile.db');
    final db = await openDatabase(
      path,
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
CREATE TABLE devices (
  device_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  status TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
''');
        await db.execute('''
CREATE TABLE messages (
  msg_id TEXT PRIMARY KEY,
  device_id TEXT NOT NULL,
  session_id TEXT,
  role TEXT NOT NULL,
  text TEXT NOT NULL,
  created_at TEXT NOT NULL
)
''');
        await db.execute(
          'CREATE INDEX idx_messages_device ON messages(device_id, created_at)',
        );
      },
    );
    return LocalDb._(db);
  }

  Future<void> upsertDevice(Device device) async {
    await _db.insert(
      'devices',
      {
        'device_id': device.deviceId,
        'name': device.name,
        'status': device.status == DeviceStatus.online ? 'online' : 'offline',
        'updated_at': DateTime.now().toIso8601String(),
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<List<Device>> listDevices() async {
    final rows = await _db.query('devices', orderBy: 'name ASC');
    return rows
        .map(
          (r) => Device(
            deviceId: r['device_id'] as String,
            name: r['name'] as String,
            status: (r['status'] as String) == 'online'
                ? DeviceStatus.online
                : DeviceStatus.offline,
          ),
        )
        .toList();
  }

  Future<void> insertMessage(ChatMessage message) async {
    await _db.insert(
      'messages',
      message.toMap(),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<List<ChatMessage>> messagesForDevice(String deviceId) async {
    final rows = await _db.query(
      'messages',
      where: 'device_id = ?',
      whereArgs: [deviceId],
      orderBy: 'created_at ASC',
    );
    return rows.map(ChatMessage.fromMap).toList();
  }

  Future<void> replaceDevices(List<Device> devices) async {
    await _db.delete('devices');
    for (final d in devices) {
      await upsertDevice(d);
    }
  }

  Future<void> clearDevices() async {
    await _db.delete('devices');
  }

  Future<void> clearMessagesForDevice(String deviceId) async {
    await _db.delete(
      'messages',
      where: 'device_id = ?',
      whereArgs: [deviceId],
    );
  }

  Future<void> close() => _db.close();
}
