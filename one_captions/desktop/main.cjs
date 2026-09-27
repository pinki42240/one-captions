const {app,BrowserWindow,dialog,ipcMain,shell,Menu}=require('electron');
const {spawn}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
let win,backend,runtime,saveFolder;
const configPath=path.join(__dirname,'config.json');
const bundledRoot=path.join(process.resourcesPath,'engine');
const standalone=fs.existsSync(path.join(bundledRoot,'one_captions','static','index.html'));
const root=standalone?bundledRoot:fs.existsSync(configPath)?JSON.parse(fs.readFileSync(configPath)).engineRoot:path.resolve(__dirname,'../..');
app.setName('ONE Captions');
if(!app.requestSingleInstanceLock())app.quit();
app.on('second-instance',()=>{if(win){win.show();win.focus();}});
async function api(route,body){
 const response=await fetch(`http://127.0.0.1:${runtime.port}${route}`,{method:'POST',headers:{'Content-Type':'application/json','X-One-Token':runtime.token},body:JSON.stringify(body)});
 const data=await response.json();if(!response.ok)throw new Error(data.error||'לא הצלחנו להשלים את הפעולה.');return data;
}
async function pickVideo(){
 const choice=await dialog.showOpenDialog(win,{title:'בחירת סרטון',properties:['openFile'],filters:[{name:'סרטונים',extensions:['mp4','mov']}]});
 return choice.canceled?null:choice.filePaths[0];
}
app.whenReady().then(async()=>{
 try{
  const preferencePath=path.join(app.getPath('userData'),'preferences.json');
  const rememberFolder=()=>{fs.mkdirSync(path.dirname(preferencePath),{recursive:true});fs.writeFileSync(preferencePath,JSON.stringify({saveFolder}));};
  try{const saved=JSON.parse(fs.readFileSync(preferencePath));if(saved.saveFolder&&fs.existsSync(saved.saveFolder))saveFolder=saved.saveFolder;}catch{}
  const backendDir=path.join(root,'one_captions');
  const userData=process.env.ONE_USER_DATA_DIR||app.getPath('userData');
  const dataDir=standalone?path.join(userData,'projects'):path.join(backendDir,'data');
  const runtimePath=path.join(dataDir,`runtime-${process.pid}.json`);
  const logPath=path.join(dataDir,'desktop.log');
  fs.mkdirSync(path.dirname(runtimePath),{recursive:true});
  const log=fs.openSync(logPath,'a');
  const python=process.platform==='win32'?path.join(root,'.venv','Scripts','python.exe'):path.join(root,'.venv','bin','python');
  const backendExe=standalone?path.join(process.resourcesPath,'runtime',process.platform==='win32'?'one-backend.exe':'one-backend'):python;
  const workerExe=standalone?backendExe:null;
  const bins=path.join(root,'bin');
  const env={...process.env,PYTHONUNBUFFERED:'1',PYTHONUTF8:'1',ONE_ENGINE_ROOT:root,ONE_DATA_DIR:dataDir,ONE_OUTPUT_DIR:path.join(dataDir,'output'),ONE_WHISPER_MODEL:path.join(dataDir,'models','hebrew'),ONE_AI_MODEL:path.join(dataDir,'models','ai','Qwen3-4B-Q4_K_M.gguf'),ONE_WORKER_BINARY:workerExe||'',ONE_LLAMA_SERVER:path.join(bins,process.platform==='win32'?'llama-server.exe':'llama-server'),PINI_FFMPEG:path.join(bins,process.platform==='win32'?'ffmpeg.exe':'ffmpeg'),PINI_FFPROBE:path.join(bins,process.platform==='win32'?'ffprobe.exe':'ffprobe'),PATH:bins+path.delimiter+process.env.PATH};
  if(standalone){
   const model=path.join(dataDir,'models','hebrew','model.bin');const ai=env.ONE_AI_MODEL;
   if(!process.env.ONE_SKIP_SETUP_TEST&&(!fs.existsSync(model)||!fs.existsSync(ai))){
    const setupWin=new BrowserWindow({width:560,height:240,resizable:false,title:'ONE Captions',backgroundColor:'#0c0e12',autoHideMenuBar:true});
    await setupWin.loadURL('data:text/html;charset=utf-8,'+encodeURIComponent('<html lang="he" dir="rtl"><body style="background:#0c0e12;color:#f1f3f5;font:16px Arial;padding:38px"><h2>ONE | CAPTIONS</h2><p id="progress">מכין את האפליקציה להפעלה הראשונה…</p></body></html>'));
    try{await new Promise((resolve,reject)=>{const setup=spawn(backendExe,['--setup',dataDir],{cwd:backendDir,env,windowsHide:true});let buffer='';setup.stdout.on('data',chunk=>{buffer+=chunk.toString();const lines=buffer.split('\n');buffer=lines.pop();for(const line of lines){try{const status=JSON.parse(line).status;setupWin.webContents.executeJavaScript(`document.getElementById('progress').textContent=${JSON.stringify(status)}`).catch(()=>{});}catch{}}});setup.stderr.on('data',chunk=>fs.appendFileSync(logPath,chunk));setup.on('error',reject);setup.on('exit',code=>code===0?resolve():reject(new Error('Model setup failed')));});}
    finally{setupWin.close();}
   }
  }
  backend=spawn(backendExe,standalone?['--runtime',runtimePath]:[path.join(backendDir,'server.py'),'--runtime',runtimePath],{cwd:backendDir,env,stdio:['ignore',log,log],windowsHide:true});
  fs.closeSync(log);
  let startError;
  backend.on('error',e=>{startError=e;});
  for(let i=0;i<200;i++){
   if(startError)throw startError;
   if(fs.existsSync(runtimePath)){runtime=JSON.parse(fs.readFileSync(runtimePath));break;}
   await new Promise(r=>setTimeout(r,100));
  }
  if(!runtime)throw new Error('startup');
  const base=`http://127.0.0.1:${runtime.port}`;
  win=new BrowserWindow({width:1360,height:930,minWidth:1000,minHeight:740,title:'ONE Captions',backgroundColor:'#0C0E12',show:false,titleBarStyle:process.platform==='darwin'?'hiddenInset':'default',trafficLightPosition:{x:18,y:21},webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true}});
  win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  win.webContents.on('will-navigate',(event,url)=>{if(!url.startsWith(base+'/'))event.preventDefault();});
  ipcMain.handle('pick-video',pickVideo);
  ipcMain.handle('pick-folder',async()=>{
   const choice=await dialog.showOpenDialog(win,{title:'איפה לשמור את הסרטונים?',properties:['openDirectory','createDirectory'],defaultPath:saveFolder||app.getPath('videos')});
   if(choice.canceled)return null;saveFolder=choice.filePaths[0];rememberFolder();return path.basename(saveFolder);
  });
  ipcMain.handle('export-target',async(_,name)=>{
   const safe=path.basename(String(name)).replace(/\.(mp4|mov)$/i,'')+' — ONE.mp4';
   const choice=await dialog.showSaveDialog(win,{title:'ייצוא הסרטון',defaultPath:path.join(saveFolder||app.getPath('videos'),safe),filters:[{name:'סרטון',extensions:['mp4']}],properties:['createDirectory','showOverwriteConfirmation']});
   if(choice.canceled)return null;saveFolder=path.dirname(choice.filePath);rememberFolder();return choice.filePath;
  });
  ipcMain.handle('open-export',async(_,id)=>{const {path:video}=await api('/api/native-result',{id});if(video)return shell.openPath(video);});
  ipcMain.handle('reveal-export',async(_,id)=>{const {path:video}=await api('/api/native-result',{id});if(video)shell.showItemInFolder(video);});
  const menu=Menu.buildFromTemplate([{label:'ONE Captions',submenu:[{role:'about'},{type:'separator'},{role:'hide'},{role:'hideOthers'},{type:'separator'},{role:'quit'}]},{label:'קובץ',submenu:[{label:'פתח סרטון…',accelerator:'CmdOrCtrl+O',click:async()=>{const p=await pickVideo();if(p)win.webContents.send('selected-video',p);}}]},{label:'עריכה',submenu:[{role:'undo'},{role:'redo'},{type:'separator'},{role:'cut'},{role:'copy'},{role:'paste'},{role:'selectAll'}]}]);
  Menu.setApplicationMenu(process.platform==='darwin'?menu:null);
  await win.loadURL(`${base}/#token=${runtime.token}`);
  win.show();win.focus();
  win.on('closed',()=>{win=null;app.quit();});
 }catch(error){dialog.showErrorBox('ONE Captions',error.message==='Model setup failed'?'המודלים לא הוכנו. בדקו את החיבור לאינטרנט ואת המקום הפנוי בדיסק, ואז פתחו את האפליקציה שוב.':'לא הצלחנו לפתוח את האפליקציה. נסו לפתוח אותה שוב.');console.error(error);app.quit();}
});
app.on('before-quit',()=>{if(backend)backend.kill();});
app.on('window-all-closed',()=>app.quit());
