// Extensión mínima: lanza la CLI del Framework de pruebas SQL (python -m app.cli) y muestra el resultado.
// Seguridad: la contraseña de Oracle se pide oculta y se pasa por variable de entorno (FW_ORACLE_PASSWORD); nunca por argumento ni se guarda.
const vscode = require('vscode');
const cp = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const salida = vscode.window.createOutputChannel('Framework SQL QA');
const SIGNIFICADO = {
  0: ['info', 'Todo PASS.'],
  1: ['warn', 'Hay comprobaciones en FAIL: se ejecutaron pero no coinciden con lo esperado.'],
  2: ['error', 'Hay ERROR: no se pudo ejecutar o evaluar (tabla inexistente, contraseña mala, sentencia prohibida…).'],
  3: ['error', 'Uso inválido: proyecto o suite inexistente, o falta la contraseña.'],
  4: ['warn', 'No había casos que ejecutar.'],
};

function carpetaApp() {
  const configurada = vscode.workspace.getConfiguration('frameworkSql').get('appPath');
  if (configurada) return configurada;
  const raiz = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0].uri.fsPath;
  if (!raiz) return null;
  const hija = path.join(raiz, 'framework-pruebas-sql');
  if (fs.existsSync(path.join(hija, 'app', 'cli.py'))) return hija;
  return fs.existsSync(path.join(raiz, 'app', 'cli.py')) ? raiz : null;
}

async function pedir(ctx, clave, mensaje, valorPorDefecto, oculto = false) {
  const previo = clave ? ctx.workspaceState.get(clave, valorPorDefecto) : '';
  const valor = await vscode.window.showInputBox({ prompt: mensaje, value: oculto ? '' : previo, password: oculto, ignoreFocusOut: true });
  if (valor === undefined || valor === '') return undefined;
  if (!oculto) await ctx.workspaceState.update(clave, valor);
  return valor;
}

function ejecutarCli(args, env) {
  const app = carpetaApp();
  if (!app) {
    vscode.window.showErrorMessage('No encuentro la carpeta framework-pruebas-sql. Abra el repositorio o configure frameworkSql.appPath.');
    return Promise.resolve(null);
  }
  const python = vscode.workspace.getConfiguration('frameworkSql').get('python') || 'python';
  salida.clear();
  salida.show(true);
  salida.appendLine(`$ ${python} -m app.cli ${args.join(' ')}`);
  return new Promise((resolver) => {
    const hijo = cp.spawn(python, ['-m', 'app.cli', ...args], { cwd: app, env: { ...process.env, ...env }, shell: false });
    hijo.stdout.on('data', (d) => salida.append(d.toString()));
    hijo.stderr.on('data', (d) => salida.append(d.toString()));
    hijo.on('error', (e) => { salida.appendLine(`No se pudo iniciar Python: ${e.message}`); resolver({ codigo: 3, app }); });
    hijo.on('close', (codigo) => resolver({ codigo, app }));
  });
}

// La CLI necesita la base interna (SQLite) con sus tablas; `init-db` la crea o la actualiza y es seguro repetirlo.
async function prepararBase() {
  const r = await ejecutarCli(['init-db']);
  if (!r) return false;
  if (r.codigo !== 0) { vscode.window.showErrorMessage('No se pudo preparar la base interna. Revise el panel «Framework SQL QA» (¿faltan las dependencias de Python?).'); return false; }
  return true;
}

async function ejecutarSuite(ctx) {
  const proyecto = await pedir(ctx, 'proyecto', 'Nombre del proyecto', 'Demo'); if (!proyecto) return;
  const suite = await pedir(ctx, 'suite', 'Nombre de la suite', 'Reglas de calidad (demo)'); if (!suite) return;
  const host = await pedir(ctx, 'host', 'Host de Oracle', '127.0.0.1'); if (!host) return;
  const puerto = await pedir(ctx, 'puerto', 'Puerto', '1521'); if (!puerto) return;
  const servicio = await pedir(ctx, 'servicio', 'Service name', 'FREEPDB1'); if (!servicio) return;
  const usuario = await pedir(ctx, 'usuario', 'Usuario de Oracle', 'FRAMEWORK_TEST'); if (!usuario) return;
  const clave = await pedir(ctx, '', 'Contraseña de Oracle (no se guarda)', '', true); if (!clave) return;
  if (!(await prepararBase())) return;
  const md = path.join(os.tmpdir(), `sql-qa-${Date.now()}.md`);
  const r = await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: 'Ejecutando la suite…' }, () =>
    ejecutarCli(['run', '--project', proyecto, '--suite', suite, '--host', host, '--port', puerto, '--service', servicio,
      '--user', usuario, '--env', 'TEST', '--markdown', md], { FW_ORACLE_PASSWORD: clave }));
  if (!r) return;
  const [nivel, texto] = SIGNIFICADO[r.codigo] || ['error', `La CLI terminó con el código ${r.codigo}.`];
  const mostrar = { info: vscode.window.showInformationMessage, warn: vscode.window.showWarningMessage, error: vscode.window.showErrorMessage }[nivel];
  if (fs.existsSync(md)) {
    const eleccion = await mostrar(`Código ${r.codigo}: ${texto}`, 'Ver reporte');
    if (eleccion === 'Ver reporte') await vscode.commands.executeCommand('markdown.showPreview', vscode.Uri.file(md));
  } else {
    mostrar(`Código ${r.codigo}: ${texto}`);
  }
}

async function importarExcel(ctx) {
  const elegido = await vscode.window.showOpenDialog({ canSelectMany: false, filters: { Excel: ['xlsx'] }, openLabel: 'Usar este Excel' });
  if (!elegido) return;
  const archivo = elegido[0].fsPath;
  const proyecto = await pedir(ctx, 'proyecto', 'Proyecto donde se importan los casos', 'Demo'); if (!proyecto) return;
  if (!(await prepararBase())) return;
  const comun = [archivo, '--project', proyecto, '--create-project', '--mode', 'update'];
  const prueba = await ejecutarCli(['import-excel', ...comun, '--dry-run']);
  if (!prueba) return;
  if (prueba.codigo !== 0) { vscode.window.showErrorMessage('El Excel tiene errores de validación. Revise el panel «Framework SQL QA»; no se guardó nada.'); return; }
  const si = await vscode.window.showInformationMessage('El Excel es válido. ¿Importar los casos?', 'Importar', 'Cancelar');
  if (si !== 'Importar') return;
  const real = await ejecutarCli(['import-excel', ...comun]);
  if (real && real.codigo === 0) vscode.window.showInformationMessage('Casos importados.');
}

async function exportarResultados(ctx) {
  const proyecto = await pedir(ctx, 'proyecto', 'Proyecto a exportar', 'Demo'); if (!proyecto) return;
  const destino = await vscode.window.showSaveDialog({ filters: { Excel: ['xlsx'] }, saveLabel: 'Guardar resultados' });
  if (!destino) return;
  if (!(await prepararBase())) return;
  const r = await ejecutarCli(['export-excel', 'results', '--project', proyecto, '--out', destino.fsPath, '--force']);
  if (r && r.codigo === 0) vscode.window.showInformationMessage('Resultados exportados.', 'Abrir').then((x) => { if (x) vscode.env.openExternal(destino); });
}

function activate(ctx) {
  ctx.subscriptions.push(
    vscode.commands.registerCommand('frameworkSql.runSuite', () => ejecutarSuite(ctx)),
    vscode.commands.registerCommand('frameworkSql.importExcel', () => importarExcel(ctx)),
    vscode.commands.registerCommand('frameworkSql.exportResults', () => exportarResultados(ctx)),
    salida);
}
function deactivate() {}
module.exports = { activate, deactivate };
