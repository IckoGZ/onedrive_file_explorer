#!/usr/bin/env python3
"""
Script de enumeración mejorado v2
- Paginación completa (SIN limitación de 20 items)
- Escaneo recursivo de carpetas por profundidad (--depth)
- Exporta a CSV: usuarios, sites, archivos con rutas completas
"""

import requests
import json
import csv
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import traceback
import argparse

csv_lock = Lock()
print_lock = Lock()

class MicrosoftGraphEnumeratorV2:
    def __init__(self, tenant_id, client_id, client_secret, max_workers=20, max_depth=2):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expires = None
        self.max_workers = max_workers
        self.max_depth = max_depth  # Profundidad de escaneo
        self.session = requests.Session()
        
    def safe_print(self, message):
        with print_lock:
            print(message)
    
    def get_access_token(self):
        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials"
        }
        
        try:
            response = self.session.post(url, data=data, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data['access_token']
                self.token_expires = token_data['expires_in']
                return True
            else:
                self.safe_print(f"[-] Error obteniendo token: {response.status_code}")
                return False
        except Exception as e:
            self.safe_print(f"[-] Excepción: {str(e)}")
            return False
    
    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    def listar_todos_los_usuarios(self):
        """Lista TODOS los usuarios con paginación"""
        self.safe_print("\n[*] Listando todos los usuarios...")
        
        url = "https://graph.microsoft.com/v1.0/users?$top=200"  # Máximo 200 por página
        usuarios = []
        page = 0
        
        while url:
            try:
                response = self.session.get(url, headers=self.get_headers(), timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    batch = data.get('value', [])
                    usuarios.extend(batch)
                    
                    self.safe_print(f"[+] Página {page + 1}: {len(batch)} usuarios")
                    page += 1
                    
                    url = data.get('@odata.nextLink')  # Siguiente página
                else:
                    self.safe_print(f"[-] Error: {response.status_code}")
                    break
            except Exception as e:
                self.safe_print(f"[-] Excepción: {str(e)}")
                break
        
        return usuarios
    
    def listar_todos_los_sites(self):
        """Lista TODOS los sites con paginación"""
        self.safe_print("\n[*] Listando todos los SharePoint Sites...")
        
        url = "https://graph.microsoft.com/v1.0/sites?$top=200"
        sites = []
        page = 0
        
        while url:
            try:
                response = self.session.get(url, headers=self.get_headers(), timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    batch = data.get('value', [])
                    sites.extend(batch)
                    
                    self.safe_print(f"[+] Página {page + 1}: {len(batch)} sites")
                    page += 1
                    
                    url = data.get('@odata.nextLink')
                else:
                    self.safe_print(f"[-] Error: {response.status_code}")
                    break
            except Exception as e:
                self.safe_print(f"[-] Excepción: {str(e)}")
                break
        
        return sites
    
    def obtener_todos_los_drives_usuario(self, user_id, user_email):
        """Obtiene TODOS los drives de un usuario"""
        drives = []
        
        try:
            # Drive personal
            try:
                url = f"https://graph.microsoft.com/v1.0/users/{user_id}/drive"
                response = self.session.get(url, headers=self.get_headers(), timeout=30)
                if response.status_code == 200:
                    drive = response.json()
                    drive['_type'] = 'personal'
                    drives.append(drive)
            except:
                pass
            
            # Todos los drives
            try:
                url = f"https://graph.microsoft.com/v1.0/users/{user_id}/drives?$top=200"
                response = self.session.get(url, headers=self.get_headers(), timeout=30)
                if response.status_code == 200:
                    user_drives = response.json().get('value', [])
                    for drive in user_drives:
                        if drive.get('id') not in [d.get('id') for d in drives]:
                            drive['_type'] = 'shared'
                            drives.append(drive)
            except:
                pass
        
        except Exception as e:
            pass
        
        return drives
    
    def listar_archivos_recursivo(self, drive_id, item_id=None, ruta="/", profundidad=0, archivos_csv=None):
        """
        Lista archivos de forma recursiva hasta profundidad máxima
        SIN limitación de 20 items por carpeta
        """
        if profundidad > self.max_depth:
            return
        
        try:
            if item_id is None:
                url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children?$top=200"
            else:
                url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/children?$top=200"
            
            items = []
            
            # Paginación completa
            while url:
                response = self.session.get(url, headers=self.get_headers(), timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    batch = data.get('value', [])
                    items.extend(batch)
                    url = data.get('@odata.nextLink')
                else:
                    break
            
            # Procesar items
            for item in items:
                try:
                    nombre = item.get('name', 'N/A')
                    ruta_completa = f"{ruta.rstrip('/')}/{nombre}"
                    tipo = 'carpeta' if 'folder' in item else 'archivo'
                    tamaño = item.get('size', 0)
                    creado = item.get('createdDateTime', '')
                    modificado = item.get('lastModifiedDateTime', '')
                    url_item = item.get('webUrl', '')
                    
                    # Guardar a CSV
                    if archivos_csv:
                        archivo_row = {
                            'drive_id': drive_id,
                            'ruta': ruta_completa,
                            'nombre': nombre,
                            'tipo': tipo,
                            'tamaño_bytes': tamaño,
                            'creado': creado,
                            'modificado': modificado,
                            'url': url_item,
                            'profundidad': profundidad,
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        with csv_lock:
                            with open(archivos_csv, 'a', newline='', encoding='utf-8') as f:
                                writer = csv.DictWriter(f, fieldnames=archivo_row.keys())
                                writer.writerow(archivo_row)
                    
                    # Recursión si es carpeta y no hemos alcanzado la profundidad máxima
                    if 'folder' in item and profundidad < self.max_depth:
                        item_id_sub = item.get('id')
                        self.listar_archivos_recursivo(drive_id, item_id_sub, ruta_completa, 
                                                      profundidad + 1, archivos_csv)
                
                except Exception as e:
                    pass
        
        except Exception as e:
            pass
    
    def procesar_usuario_paralelo(self, usuario, usuarios_csv, archivos_csv):
        """Procesa un usuario y todos sus drives"""
        try:
            user_id = usuario.get('id')
            user_name = usuario.get('displayName', 'N/A')
            user_email = usuario.get('userPrincipalName', '')
            
            # Obtener TODOS los drives
            drives = self.obtener_todos_los_drives_usuario(user_id, user_email)
            
            for drive in drives:
                try:
                    drive_id = drive.get('id')
                    drive_name = drive.get('name', 'N/A')
                    drive_url = drive.get('webUrl', '')
                    drive_type = drive.get('_type', 'unknown')
                    quota_info = drive.get('quota', {}) or {}
                    quota_total = quota_info.get('total', 0) or 0
                    quota_used = quota_info.get('used', 0) or 0
                    
                    if quota_total > 0:
                        porcentaje = (quota_used / quota_total) * 100
                    else:
                        porcentaje = 0
                    
                    # Guardar drive
                    user_row = {
                        'user_id': user_id,
                        'nombre': user_name,
                        'email': user_email,
                        'drive_id': drive_id,
                        'drive_name': drive_name,
                        'drive_type': drive_type,
                        'drive_url': drive_url,
                        'quota_usado_gb': round(quota_used / 1024**3, 2) if quota_used else 0,
                        'quota_total_gb': round(quota_total / 1024**3, 2) if quota_total else 0,
                        'porcentaje_uso': round(porcentaje, 2),
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    with csv_lock:
                        with open(usuarios_csv, 'a', newline='', encoding='utf-8') as f:
                            writer = csv.DictWriter(f, fieldnames=user_row.keys())
                            writer.writerow(user_row)
                    
                    # Escanear archivos de forma RECURSIVA
                    self.listar_archivos_recursivo(drive_id, None, "/", 0, archivos_csv)
                    
                    self.safe_print(f"[+] {user_email}: Drive '{drive_name}' procesado")
                
                except Exception as e:
                    self.safe_print(f"[-] Error procesando drive: {str(e)}")
            
            if len(drives) == 0:
                self.safe_print(f"[-] {user_email}: Sin drives")
        
        except Exception as e:
            self.safe_print(f"[-] Error: {str(e)}")
    
    def procesar_site_paralelo(self, site, sites_csv, archivos_csv):
        """Procesa un site"""
        try:
            site_id = site.get('id')
            site_name = site.get('displayName', 'N/A')
            site_url = site.get('webUrl', '')
            
            # Obtener drives del site
            try:
                drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives?$top=200"
                
                drives = []
                url = drives_url
                
                while url:
                    response = self.session.get(url, headers=self.get_headers(), timeout=30)
                    if response.status_code == 200:
                        data = response.json()
                        drives.extend(data.get('value', []))
                        url = data.get('@odata.nextLink')
                    else:
                        break
                
                for drive in drives:
                    try:
                        drive_id = drive.get('id')
                        drive_name = drive.get('name', 'N/A')
                        drive_type = drive.get('driveType', 'N/A')
                        quota_info = drive.get('quota', {}) or {}
                        quota_total = quota_info.get('total', 0) or 0
                        quota_used = quota_info.get('used', 0) or 0
                        
                        if quota_total > 0:
                            porcentaje = (quota_used / quota_total) * 100
                        else:
                            porcentaje = 0
                        
                        site_row = {
                            'tipo': 'SITE',
                            'nombre': site_name,
                            'email': '',
                            'url': site_url,
                            'drive_id': drive_id,
                            'drive_name': drive_name,
                            'drive_type': drive_type,
                            'quota_usado_gb': round(quota_used / 1024**3, 2) if quota_used else 0,
                            'quota_total_gb': round(quota_total / 1024**3, 2) if quota_total else 0,
                            'porcentaje_uso': round(porcentaje, 2),
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        with csv_lock:
                            with open(sites_csv, 'a', newline='', encoding='utf-8') as f:
                                writer = csv.DictWriter(f, fieldnames=site_row.keys())
                                writer.writerow(site_row)
                        
                        # Escanear archivos RECURSIVAMENTE
                        self.listar_archivos_recursivo(drive_id, None, "/", 0, archivos_csv)
                        
                        self.safe_print(f"[+] Site: {site_name} -> Drive: {drive_name}")
                    
                    except Exception as e:
                        pass
            
            except Exception as e:
                pass
        
        except Exception as e:
            self.safe_print(f"[-] Error: {str(e)}")
    
    def generar_reporte_completo(self):
        """Genera reporte completo"""
        
        self.safe_print("\n" + "=" * 100)
        self.safe_print(f"ENUMERACIÓN COMPLETA - PROFUNDIDAD: {self.max_depth} NIVELES")
        self.safe_print("=" * 100)
        
        # Crear archivos CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        usuarios_csv = f"usuarios_{timestamp}.csv"
        sites_csv = f"sites_{timestamp}.csv"
        archivos_csv = f"archivos_{timestamp}.csv"
        
        # Headers
        usuarios_headers = ['user_id', 'nombre', 'email', 'drive_id', 'drive_name', 'drive_type',
                           'drive_url', 'quota_usado_gb', 'quota_total_gb', 'porcentaje_uso', 'timestamp']
        sites_headers = ['tipo', 'nombre', 'email', 'url', 'drive_id', 'drive_name', 'drive_type',
                        'quota_usado_gb', 'quota_total_gb', 'porcentaje_uso', 'timestamp']
        archivos_headers = ['drive_id', 'ruta', 'nombre', 'tipo', 'tamaño_bytes', 'creado', 
                           'modificado', 'url', 'profundidad', 'timestamp']
        
        # Crear CSVs
        for filename, headers in [(usuarios_csv, usuarios_headers),
                                 (sites_csv, sites_headers),
                                 (archivos_csv, archivos_headers)]:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
        
        # Autenticar
        self.safe_print("\n[1] Autenticando...")
        if not self.get_access_token():
            return
        
        self.safe_print(f"[+] Token válido por: {self.token_expires}s")
        
        # Listar usuarios
        self.safe_print("\n[2] Enumerando usuarios...")
        usuarios = self.listar_todos_los_usuarios()
        self.safe_print(f"[+] Total: {len(usuarios)}")
        
        # Listar sites
        self.safe_print("\n[3] Enumerando sites...")
        sites = self.listar_todos_los_sites()
        self.safe_print(f"[+] Total: {len(sites)}")
        
        # Procesar usuarios
        self.safe_print(f"\n[4] Procesando usuarios (profundidad: {self.max_depth})...")
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(self.procesar_usuario_paralelo, usuario, usuarios_csv, archivos_csv)
                      for usuario in usuarios]
            completed = 0
            for future in as_completed(futures):
                completed += 1
                if completed % 50 == 0:
                    self.safe_print(f"[*] {completed}/{len(usuarios)}")
        
        # Procesar sites
        self.safe_print(f"\n[5] Procesando sites (profundidad: {self.max_depth})...")
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(self.procesar_site_paralelo, site, sites_csv, archivos_csv)
                      for site in sites]
            completed = 0
            for future in as_completed(futures):
                completed += 1
                if completed % 5 == 0:
                    self.safe_print(f"[*] {completed}/{len(sites)}")
        
        # Resumen
        self.safe_print("\n" + "=" * 100)
        self.safe_print("RESUMEN FINAL")
        self.safe_print("=" * 100)
        
        for filename in [usuarios_csv, sites_csv, archivos_csv]:
            if os.path.exists(filename):
                size = os.path.getsize(filename)
                with open(filename, 'r', encoding='utf-8') as f:
                    lines = len(f.readlines()) - 1
                self.safe_print(f"[+] {filename}: {lines} registros ({size:,} bytes)")
        
        self.safe_print(f"\n[+] Completado")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MS Graph Enumerator v2')
    parser.add_argument('--tenant-id', required=True)
    parser.add_argument('--client-id', required=True)
    parser.add_argument('--client-secret', required=True)
    parser.add_argument('--workers', type=int, default=20, help='Número de threads (default: 20)')
    parser.add_argument('--depth', type=int, default=2, help='Profundidad de escaneo de carpetas (default: 2)')
    
    args = parser.parse_args()
    
    enumerator = MicrosoftGraphEnumeratorV2(
        tenant_id=args.tenant_id,
        client_id=args.client_id,
        client_secret=args.client_secret,
        max_workers=args.workers,
        max_depth=args.depth
    )
    
    enumerator.generar_reporte_completo()
