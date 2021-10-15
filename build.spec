# -*- mode: python ; coding: utf-8 -*-


block_cipher = pyi_crypto.PyiBlockCipher(key='vz4a5mutt6e6bgfw')

datas = [
    ('core\\protocol\\lz77cpp.cxx', '.\\core\\protocol'),
    ('core\\templates\\base.html', '.\\core\\templates'),
    ('core\\templates\\index.html', '.\\core\\templates')
]

hiddenimports = [
    'aiosqlite',
    'python-multipart',
    'core.backend',
    'core.frontend',
    'plugins.iidx',
    'plugins.iidx.webui'
]

a = Analysis(['main.py'],
             pathex=['venv', 'D:\\workspace\\python\\oxygen'],
             binaries=[],
             datas=datas,
             hiddenimports=hiddenimports,
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,  
          [],
          name='Oxygen',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None )
