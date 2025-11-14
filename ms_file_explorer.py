#!/usr/bin/env python3
"""
Microsoft Graph Explorer v8
- Soporte para nombres con espacios usando comillas
- Mejor manejo de la entrada
"""

import requests
import os
import sys
import shlex  # Para parsear comandos con espacios correctamente
from datetime import datetime

class SharePointExplorerV8:
    def __init__(self, tenant_id, client_id, client_secret, drive_id_or_url=None):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.drive_id = None
        self.current_item_id = None
        self.current_path = "/"
        self.available_drives = []
        
        if not self.authenticate():
            print("[-] Error de autenticación")
            sys.exit(1)
        
        if drive_id_or_url:
            drive_id_clean = drive_id_or_url.strip().strip('"').strip("'")
            
            if drive_id_clean.startswith('b!'):
                self.drive_id = drive_id_clean
                print(f"[+] Drive ID cargado: {self.drive_id[:30]}...")
            else:
                if not self.get_drives_from_url(drive_id_clean):
                    print("[-] Error obteniendo drives")
                    sys.exit(1)
    
    def authenticate(self):
        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials"
        }
        
        try:
            response = requests.post(url, data=data, timeout=30)
            if response.status_code == 200:
                self.access_token = response.json()['access_token']
                print("[+] Autenticado correctamente")
                return True
            return False
        except Exception as e:
            print(f"[-] Error: {str(e)}")
            return False
    
    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    def search_all_drives_by_email(self, email):
        """Busca drives globalmente por email"""
        print(f"\n[*] Buscando todos los drives del tenant...")
        drives = []
        
        try:
            print(f"[*] Intentando búsqueda global en sites...")
            
            search_url = f"https://graph.microsoft.com/v1.0/sites?$search=\"{email}\""
            response = requests.get(search_url, headers=self.get_headers(), timeout=30)
            
            print(f"[*] Status búsqueda sites: {response.status_code}")
            
            if response.status_code == 200:
                sites = response.json().get('value', [])
                print(f"[+] Sites encontrados: {len(sites)}")
                
                for site in sites:
                    print(f"[*] Site: {site.get('displayName', 'N/A')}")
                    
                    try:
                        site_id = site.get('id')
                        drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
                        drives_response = requests.get(drives_url, headers=self.get_headers(), timeout=30)
                        
                        if drives_response.status_code == 200:
                            site_drives = drives_response.json().get('value', [])
                            drives.extend(site_drives)
                            print(f"    [+] Drives encontrados: {len(site_drives)}")
                    except Exception as e:
                        print(f"    [-] Error: {str(e)}")
        
        except Exception as e:
            print(f"[-] Error búsqueda global: {str(e)}")
        
        return drives
    
    def get_drives_from_url(self, onedrive_url):
        """Obtiene drives desde URL"""
        try:
            print(f"\n[*] Procesando URL: {onedrive_url}")
            
            onedrive_url = onedrive_url.rstrip('/')
            
            if '/personal/' not in onedrive_url:
                print("[-] URL no contiene /personal/")
                return False
            
            personal_part = onedrive_url.split('/personal/')[-1]
            print(f"[*] Email path: {personal_part}")
            
            parts = personal_part.split('_')
            if len(parts) < 3:
                print("[-] Formato inválido")
                return False
            
            tld = parts[-1]
            domain = parts[-2]
            name_parts = parts[:-2]
            
            email = '.'.join(name_parts) + '@' + domain + '.' + tld
            print(f"[*] Email: {email}")
            
            # MÉTODO 1: Búsqueda normal
            print(f"[*] Intentando búsqueda normal...")
            users_url = f"https://graph.microsoft.com/v1.0/users?$filter=mail eq '{email}' or userPrincipalName eq '{email}'"
            users_response = requests.get(users_url, headers=self.get_headers(), timeout=30)
            
            print(f"[*] Status búsqueda usuario: {users_response.status_code}")
            
            if users_response.status_code == 200:
                users = users_response.json().get('value', [])
                
                if users:
                    user_id = users[0]['id']
                    user_name = users[0].get('displayName', email)
                    print(f"[+] Usuario encontrado: {user_name}")
                    
                    return self.get_user_drives(user_id, user_name)
                else:
                    print(f"[-] Usuario no encontrado (probablemente eliminado)")
            
            elif users_response.status_code == 403:
                print(f"[-] Acceso denegado (403)")
            
            # MÉTODO 2: Búsqueda global
            print(f"\n[*] Intentando búsqueda global...")
            drives = self.search_all_drives_by_email(email)
            
            if drives:
                self.available_drives = []
                for drive in drives:
                    self.available_drives.append({
                        'id': drive.get('id'),
                        'name': drive.get('name', 'Drive'),
                        'type': 'huerfano',
                        'owner': email,
                        'quota': drive.get('quota', {})
                    })
                
                print(f"\n[+] Drives encontrados: {len(self.available_drives)}")
                
                if len(self.available_drives) == 1:
                    self.drive_id = self.available_drives[0]['id']
                    print(f"[+] Drive seleccionado: {self.available_drives[0]['name']}")
                    return True
                else:
                    return self.select_drive()
            
            print("[-] No se encontraron drives")
            return False
            
        except Exception as e:
            print(f"[-] Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_user_drives(self, user_id, user_name):
        """Obtiene drives de usuario"""
        self.available_drives = []
        
        try:
            drive_url = f"https://graph.microsoft.com/v1.0/users/{user_id}/drive"
            drive_response = requests.get(drive_url, headers=self.get_headers(), timeout=30)
            
            if drive_response.status_code == 200:
                drive = drive_response.json()
                self.available_drives.append({
                    'id': drive.get('id'),
                    'name': f"{user_name} - OneDrive Personal",
                    'type': 'personal',
                    'owner': user_name,
                    'quota': drive.get('quota', {})
                })
        except:
            pass
        
        try:
            drives_url = f"https://graph.microsoft.com/v1.0/users/{user_id}/drives"
            drives_response = requests.get(drives_url, headers=self.get_headers(), timeout=30)
            
            if drives_response.status_code == 200:
                user_drives = drives_response.json().get('value', [])
                for drive in user_drives:
                    if not any(d['id'] == drive.get('id') for d in self.available_drives):
                        self.available_drives.append({
                            'id': drive.get('id'),
                            'name': drive.get('name', 'Drive'),
                            'type': 'shared',
                            'owner': user_name,
                            'quota': drive.get('quota', {})
                        })
        except:
            pass
        
        print(f"\n[+] Drives encontrados: {len(self.available_drives)}")
        
        if len(self.available_drives) == 0:
            return False
        
        if len(self.available_drives) == 1:
            self.drive_id = self.available_drives[0]['id']
            return True
        
        return self.select_drive()
    
    def select_drive(self):
        """Menú de selección de drives"""
        print("\n" + "=" * 80)
        print("DRIVES DISPONIBLES:")
        print("=" * 80)
        
        for i, drive in enumerate(self.available_drives, 1):
            quota = drive.get('quota', {})
            quota_total = quota.get('total', 0)
            quota_used = quota.get('used', 0)
            
            if quota_total > 0:
                used_gb = quota_used / (1024**3)
                total_gb = quota_total / (1024**3)
                percent = (quota_used / quota_total) * 100
                quota_str = f"{used_gb:.1f}GB / {total_gb:.1f}GB ({percent:.1f}%)"
            else:
                quota_str = "Sin límite"
            
            print(f"\n[{i}] {drive['name']}")
            print(f"    Tipo: {drive['type']}")
            print(f"    ID: {drive['id'][:40]}...")
            print(f"    Uso: {quota_str}")
        
        print("\n" + "=" * 80)
        
        try:
            choice = input("Selecciona drive (Enter=1): ").strip()
            
            if not choice:
                choice = "1"
            
            if choice.isdigit() and 1 <= int(choice) <= len(self.available_drives):
                self.drive_id = self.available_drives[int(choice) - 1]['id']
                return True
            
            return False
        except KeyboardInterrupt:
            return False
    
    def list_files(self, item_id=None):
        """Lista archivos con paginación completa"""
        try:
            if not self.drive_id:
                return []
            
            if item_id is None:
                url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root/children"
            else:
                url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/items/{item_id}/children"
            
            url += "?$top=200"
            
            items = []
            
            while url:
                response = requests.get(url, headers=self.get_headers(), timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    items.extend(data.get('value', []))
                    url = data.get('@odata.nextLink')
                else:
                    break
            
            return items
        
        except Exception as e:
            print(f"[-] Error: {str(e)}")
            return []
    
    def get_item_by_name(self, name, items):
        """Busca item por nombre (con espacios)"""
        # Búsqueda exacta
        for item in items:
            if item.get('name', '').lower() == name.lower():
                return item
        return None
    
    def cmd_dir(self):
        """Comando: dir"""
        if not self.drive_id:
            print("[-] No hay drive")
            return
        
        items = self.list_files(self.current_item_id)
        
        if not items:
            print("[*] Carpeta vacía")
            return
        
        print(f"\nDirectorio: {self.current_path}")
        print(f"Total items: {len(items)}\n")
        print(f"{'TIPO':<10} {'NOMBRE':<50} {'TAMAÑO':<15} {'MODIFICADO':<20}")
        print("-" * 95)
        
        for item in items:
            name = item.get('name', 'N/A')[:48]
            tamaño = item.get('size', 0) if 'file' in item else 0
            fecha = item.get('lastModifiedDateTime', 'N/A')[:10]
            tipo = "📁" if 'folder' in item else "📄"
            
            if tamaño > 0:
                if tamaño < 1024*1024:
                    tamaño_str = f"{tamaño / 1024:.1f}KB"
                else:
                    tamaño_str = f"{tamaño / (1024*1024):.1f}MB"
            else:
                tamaño_str = ""
            
            print(f"{tipo:<10} {name:<50} {tamaño_str:<15} {fecha:<20}")
        print()
    
    def cmd_cd(self, target):
        """Comando: cd - Soporta espacios en nombres"""
        if not self.drive_id:
            return
        
        # Manejar cd ..
        if target == "..":
            if self.current_path != "/":
                parts = self.current_path.rstrip('/').split('/')
                # Encontrar el item_id del padre
                if len(parts) > 1:
                    self.current_path = '/'.join(parts[:-1]) or "/"
                else:
                    self.current_path = "/"
                self.current_item_id = None
                print(f"[+] {self.current_path}")
            return
        
        if target == "/":
            self.current_path = "/"
            self.current_item_id = None
            return
        
        items = self.list_files(self.current_item_id)
        item = self.get_item_by_name(target, items)
        
        if not item:
            print(f"[-] No existe: {target}")
            return
        
        if 'folder' not in item:
            print(f"[-] No es carpeta: {target}")
            return
        
        self.current_item_id = item.get('id')
        self.current_path = f"{self.current_path.rstrip('/')}/{target}"
        print(f"[+] {self.current_path}")
    
    def cmd_download(self, filename):
        """Comando: download - Soporta espacios en nombres"""
        if not self.drive_id:
            return
        
        items = self.list_files(self.current_item_id)
        item = self.get_item_by_name(filename, items)
        
        if not item:
            print(f"[-] No existe: {filename}")
            return
        
        if 'folder' in item:
            print(f"[-] Es carpeta, no archivo")
            return
        
        try:
            item_id = item.get('id')
            url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/items/{item_id}/content"
            
            print(f"[*] Descargando {filename}...")
            response = requests.get(url, headers=self.get_headers(), timeout=60, stream=True)
            
            if response.status_code == 200:
                # Obtener tamaño total
                total_size = int(response.headers.get('content-length', 0))
                
                with open(filename, 'wb') as f:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = (downloaded / total_size) * 100
                                print(f"[*] Progreso: {percent:.1f}%", end='\r')
                
                print(f"[+] Descargado: {filename} ({total_size/1024:.1f}KB)  ")
            else:
                print(f"[-] Error: {response.status_code}")
        except Exception as e:
            print(f"[-] Error: {str(e)}")
    
    def cmd_pwd(self):
        print(f"Ubicación: {self.current_path}")
        if self.drive_id:
            print(f"Drive: {self.drive_id}")
    
    def cmd_help(self):
        print("""
Comandos:
  dir                  - Listar contenido
  cd <carpeta>         - Navegar (usa comillas: cd "Carpeta con espacios")
  cd ..                - Ir atrás
  cd /                 - Ir a raíz
  download <archivo>   - Descargar (usa comillas si tiene espacios)
  pwd                  - Ruta actual
  help                 - Esta ayuda
  exit                 - Salir

NOTA: Para archivos/carpetas con espacios, usa comillas:
  cd "My Documents"
  download "Mi archivo.pdf"
        """)
    
    def parse_command(self, line):
        """
        Parsea comandos correctamente soportando comillas
        Retorna: (comando, argumento)
        """
        try:
            # Usar shlex para parsear respetando comillas
            parts = shlex.split(line)
            if not parts:
                return None, None
            
            command = parts[0].lower()
            arg = ' '.join(parts[1:]) if len(parts) > 1 else None
            
            return command, arg
        except ValueError:
            # Si hay error de comillas mal formadas
            print("[-] Error: Comillas mal formadas")
            return None, None
    
    def run(self):
        """Loop principal mejorado"""
        if not self.drive_id:
            print("[-] No hay drive")
            return
        
        print(f"\n[+] Conectado")
        print(f"[+] Ubicación: {self.current_path}")
        print("[+] 'help' para ver comandos\n")
        
        while True:
            try:
                cmd_line = input(f"explorer:{self.current_path}> ").strip()
                
                if not cmd_line:
                    continue
                
                command, arg = self.parse_command(cmd_line)
                
                if command is None:
                    continue
                
                if command == "dir":
                    self.cmd_dir()
                elif command == "cd":
                    if arg:
                        self.cmd_cd(arg)
                    else:
                        print("[-] Uso: cd <carpeta>")
                elif command == "download":
                    if arg:
                        self.cmd_download(arg)
                    else:
                        print("[-] Uso: download <archivo>")
                elif command == "pwd":
                    self.cmd_pwd()
                elif command == "help":
                    self.cmd_help()
                elif command in ["exit", "quit"]:
                    print("[+] Adiós!")
                    break
                else:
                    print(f"[-] {command}: desconocido")
            
            except KeyboardInterrupt:
                print("\n[+] Adiós!")
                break
            except Exception as e:
                print(f"[-] Error: {str(e)}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='MS Graph Explorer v8')
    parser.add_argument('--tenant-id', required=True)
    parser.add_argument('--client-id', required=True)
    parser.add_argument('--client-secret', required=True)
    parser.add_argument('--drive-id', help='Drive ID')
    parser.add_argument('--url', help='OneDrive URL')
    
    args = parser.parse_args()
    
    drive_input = args.drive_id or args.url
    
    if not drive_input:
        print("[-] Necesitas --drive-id o --url")
        sys.exit(1)
    
    explorer = SharePointExplorerV8(
        tenant_id=args.tenant_id,
        client_id=args.client_id,
        client_secret=args.client_secret,
        drive_id_or_url=drive_input
    )
    
    explorer.run()
