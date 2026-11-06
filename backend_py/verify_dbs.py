import psycopg2
import mysql.connector

try:
    pg = psycopg2.connect(host='localhost', port=5432, dbname='bd1_diagnosticos', user='admin_pg', password='SecretPassword123!')
    with pg.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM historial_diagnosticos')
        pg_count = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM metadatos_imagen')
        meta_count = cur.fetchone()[0]
    pg.close()
    print(f'[+] BD1 PostgreSQL: {pg_count} diagnosticos guardados, {meta_count} metadatos de imagenes.')
except Exception as e:
    print('[-] Error BD1:', e)

try:
    maria = mysql.connector.connect(host='localhost', port=3306, database='bd2_validacion', user='admin_maria', password='SecretPassword123!')
    cur_m = maria.cursor()
    cur_m.execute('SELECT COUNT(*) FROM registro_validaciones')
    maria_count = cur_m.fetchone()[0]
    maria.close()
    print(f'[+] BD2 MariaDB: {maria_count} solicitudes de validacion auditadas con exito.')
except Exception as e:
    print('[-] Error BD2:', e)
