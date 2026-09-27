const {contextBridge,ipcRenderer,webUtils}=require('electron');
contextBridge.exposeInMainWorld('oneDesktop',{
 pickVideo:()=>ipcRenderer.invoke('pick-video'),
 pickFolder:()=>ipcRenderer.invoke('pick-folder'),
 exportTarget:name=>ipcRenderer.invoke('export-target',name),
 openExport:id=>ipcRenderer.invoke('open-export',id),
 revealExport:id=>ipcRenderer.invoke('reveal-export',id),
 pathForFile:file=>webUtils.getPathForFile(file),
 onSelectedVideo:callback=>ipcRenderer.on('selected-video',(_,p)=>callback(p))
});
