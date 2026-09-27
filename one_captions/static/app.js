'use strict';
window.__consoleErrors=[];window.addEventListener('error',e=>window.__consoleErrors.push(e.message));window.addEventListener('unhandledrejection',e=>window.__consoleErrors.push(String(e.reason)));
const $=id=>document.getElementById(id);
const token=new URLSearchParams(location.hash.slice(1)).get('token')||new URLSearchParams(location.search).get('token');
const desktop=window.oneDesktop;
let chatPending=false;
let session=null,poller=null,resultMode=false,editingIndex=null,lastMessages='',lastCues='',lastPreview='',lastJobStatus='',toastTimer;
let captionOccurrences=[],occurrenceCues=null;
const video=$('video');
function toast(text){$('toast').textContent=text;$('toast').classList.remove('hidden');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.add('hidden'),6500);}
async function api(route,data){
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),route==='/api/chat'?100000:route==='/api/import'?600000:20000);
 try{const r=await fetch(route,{method:data?'POST':'GET',signal:controller.signal,headers:{'X-One-Token':token,...(data?{'Content-Type':'application/json'}:{})},body:data?JSON.stringify(data):undefined});const out=await r.json();if(!r.ok)throw new Error(out.error||'לא הצלחנו להשלים את הפעולה.');return out;}
 catch(e){if(e.name==='AbortError')throw new Error('הבקשה לא הושלמה בזמן. התיקונים נשמרו. אפשר לשלוח שוב.');throw e;}
 finally{clearTimeout(timer);}
}
function time(seconds){seconds=Math.max(0,Number(seconds)||0);return `${Math.floor(seconds/60)}:${String(Math.floor(seconds%60)).padStart(2,'0')}`;}
function media(mode){return `/media/${session.id}/${mode}?token=${encodeURIComponent(token)}`;}
function colorFromASS(s){const h=s.replace('&H','').replace(/&$/,'').padStart(8,'0');return '#'+h.slice(6,8)+h.slice(4,6)+h.slice(2,4);}
function normalize(text){return text.replace(/[^\p{L}\p{N}]/gu,'').toLowerCase();}
function captionShadow(shadow=0,glow=0,color='#FFFFFF',scale=1){shadow*=scale;glow*=scale;const parts=[];if(shadow)parts.push(`${shadow}px ${shadow}px 0 #0008`);if(glow)parts.push(`0 0 ${glow}px ${color}`,`0 0 ${glow*2}px ${color}`);return parts.join(',')||'none';}
function applyCaption(){
 if(!session)return;
 const overlay=$('caption-overlay');if(resultMode){overlay.style.display='none';if(typeof updateDirect==='function')updateDirect();return;}overlay.style.display='block';
 const width=$('video-container').getBoundingClientRect().width;
 const settings=session.settings;
 overlay.style.fontSize=(width*settings.font_size_ratio)+'px';overlay.style.bottom=(settings.bottom_margin_ratio*100)+'%';
 overlay.style.left=((settings.center_x_ratio??.5)*100)+'%';overlay.style.right='auto';overlay.style.width=(settings.max_width_ratio*100)+'%';overlay.style.whiteSpace='pre';overlay.style.transform='translateX(-50%)';
 overlay.style.fontWeight=settings.bold?'700':'400';overlay.style.color=colorFromASS(settings.primary_color);overlay.style.fontStyle=settings.italic?'italic':'normal';overlay.style.textDecoration='none';overlay.style.textShadow=captionShadow(settings.shadow,settings.glow,colorFromASS(settings.primary_color),width/session.width);
 const outline=width*settings.font_size_ratio*settings.outline_ratio;
 overlay.style.webkitTextStroke=`${Math.max(0,outline)}px ${colorFromASS(settings.outline_color)}`;overlay.style.paintOrder='stroke fill';
 const cue=session.cues.find(c=>video.currentTime>=c.start&&video.currentTime<c.end);
 const lines=cue?cue.lines:session.cues.length?[]:['ככה ייראו הכתוביות שלך'];
 overlay.replaceChildren();
 if(occurrenceCues!==session.cues){occurrenceCues=session.cues;const counts={};captionOccurrences=session.cues.map(c=>c.lines.join(' ').split(/\s+/).map(w=>{const key=normalize(w);counts[key]=(counts[key]||0)+1;return counts[key];}));}
 const important=new Set(session.important_words||[]);let tokenIndex=0;const runs=cue?(session.word_runs||[])[session.cues.indexOf(cue)]||[]:[];
 lines.forEach((line,i)=>{
  if(i)overlay.append(document.createElement('br'));
  line.split(/(\s+)/).forEach(word=>{const span=document.createElement('span');span.textContent=word;const k=normalize(word),color=session.colors[k]||(important.has(k)?'#CAED65':null);if(color){span.style.color=color;span.style.fontWeight='700';}if(word.trim()){const ti=tokenIndex++,st=runs[ti]||{};span.dataset.word=word;span.dataset.cue=session.cues.indexOf(cue);span.dataset.token=ti;span.dataset.occurrence=captionOccurrences[Number(span.dataset.cue)]?.[ti]||1;if(typeof direct!=='undefined'&&direct.word&&normalize(direct.word.word)===k&&direct.word.occurrence===Number(span.dataset.occurrence))span.classList.add('word-selected');span.style.textDecoration=(st.underline??settings.underline)?'underline':'none';if(st.color)span.style.color=st.color;for(const [key,prop,on,off] of [['bold','fontWeight','700','400'],['italic','fontStyle','italic','normal'],['underline','textDecoration','underline','none']])if(key in st)span.style[prop]=st[key]?on:off;if(st.font_size||st.scale)span.style.fontSize=((st.font_size?width*st.font_size/session.width:width*settings.font_size_ratio)*(st.scale||1))+'px';if('opacity' in st)span.style.opacity=st.opacity;if('outline' in st||st.outline_color)span.style.webkitTextStroke=('outline' in st?st.outline*width/session.width:Math.max(0,outline))+'px '+(st.outline_color||colorFromASS(settings.outline_color));if('shadow' in st||'glow' in st)span.style.textShadow=captionShadow(st.shadow??settings.shadow,st.glow??settings.glow,st.color||colorFromASS(settings.primary_color),width/session.width);}overlay.append(span);});
 });
 if(!session.cues.length)overlay.style.opacity='.8';else overlay.style.opacity=String(settings.opacity??1);
 if(typeof updateDirect==='function')updateDirect();
 document.querySelectorAll('.cue-row').forEach(el=>el.classList.toggle('current',cue&&Number(el.dataset.index)===session.cues.indexOf(cue)));
}
function setMode(result){resultMode=result;$('source-mode').classList.toggle('active',!result);$('result-mode').classList.toggle('active',result);const previousTime=video.currentTime;const playing=!video.paused;lastPreview='';setVideo();video.addEventListener('loadedmetadata',()=>{video.currentTime=Math.min(previousTime,video.duration||0);if(playing)video.play().catch(()=>{});},{once:true});applyCaption();}
function setVideo(){
 if(!session)return;
 const src=resultMode&&session.has_export?media('export'):session.preview_ready?media('preview'):'';
 if(src&&src!==lastPreview){lastPreview=src;video.src=src;video.load();}
 $('preview-loading').classList.toggle('hidden',Boolean(src));
 if(session.preview_error&&!src){$('preview-loading').querySelector('span').textContent=session.preview_error;$('preview-loading').querySelector('.spinner').classList.add('hidden');}else{$('preview-loading').querySelector('span').textContent='מכין תצוגה מקדימה';$('preview-loading').querySelector('.spinner').classList.remove('hidden');}$('play-overlay').classList.toggle('hidden',!src||!video.paused);
}
function renderChat(){
 const key=JSON.stringify([session.messages,session.thinking||chatPending]);if(key===lastMessages)return;lastMessages=key;
 const list=$('chat-list');list.replaceChildren();
 session.messages.forEach(m=>{const article=document.createElement('article');article.className='chat-message '+m.role;const label=document.createElement('div');label.className='message-label';label.textContent=m.role==='user'?'את/ה':'✦ העוזר של ONE';const bubble=document.createElement('div');bubble.className='bubble';bubble.textContent=m.text;article.append(label,bubble);list.append(article);});
 if(session.thinking||chatPending){const article=document.createElement('article');article.className='chat-message assistant';const bubble=document.createElement('div');bubble.className='bubble';bubble.textContent='חושב על השינוי שלך…';article.append(bubble);list.append(article);}
 list.scrollTop=list.scrollHeight;
}
function renderCues(){
 const key=JSON.stringify(session.cues);if(key===lastCues)return;lastCues=key;
 const list=$('caption-list');list.replaceChildren();$('cue-count').textContent=session.cues.length;
 if(!session.cues.length){const empty=document.createElement('div');empty.className='empty-captions';empty.textContent='המילים מהסרטון יופיעו כאן אחרי יצירת הכתוביות.';list.append(empty);return;}
 session.cues.forEach((cue,index)=>{const row=document.createElement('button');row.className='cue-row';row.dataset.index=index;row.title='עריכת שורת כתוביות';const t=document.createElement('span');t.className='cue-time';t.textContent=time(cue.start);const text=document.createElement('span');text.className='cue-text';text.textContent=cue.lines.join('\n');const pencil=document.createElement('span');pencil.className='cue-edit';pencil.textContent='✎';row.append(t,text,pencil);row.onclick=()=>editCue(index);list.append(row);});
}
function applySession(next,force=false){
 if(!force&&typeof directBusy==='function'&&directBusy())return;
 if(session?.id===next.id&&next.revision<session.revision)return;
 const changedSession=!session||session.id!==next.id;
 session=next;
 if(changedSession){if(typeof direct!=='undefined'){direct.selected=false;direct.word=null;direct.wordMode=false;}resultMode=false;lastPreview='';lastMessages='';lastCues='';lastJobStatus='';localStorage.setItem('one-current-session',session.id);}
 $('welcome').classList.add('hidden');$('workspace').classList.remove('hidden');$('export-button').classList.remove('hidden');
 $('home-button').classList.remove('hidden');$('video-name').textContent=session.name;$('duration').textContent=time(session.duration);$('seek').max=session.duration;
 $('video-container').style.aspectRatio=`${session.width}/${session.height}`;
 const processing=session.job.status==='running';const busy=processing||session.thinking||chatPending||(typeof directBusy==='function'&&directBusy());
 $('export-button').disabled=busy||!session.has_captions;$('undo').classList.remove('hidden');$('undo').disabled=!session.can_undo||busy;
 $('redo').classList.remove('hidden');$('redo').disabled=!session.can_redo||busy;
 $('chat-input').placeholder=session.thinking||chatPending?'חושב על השינוי שלך…':'מה תרצו לשנות?';
 $('chat-input').disabled=busy;document.querySelector('.send-btn').disabled=busy;$('generate').disabled=busy;
 $('generate').classList.toggle('hidden',session.has_captions||busy);
 $('progress-card').classList.toggle('hidden',!processing);$('progress-phase').textContent=session.job.phase||'מכין את הסרטון';$('progress-value').textContent=`${Math.round(session.job.percent||0)}%`;$('progress-fill').style.width=`${session.job.percent||0}%`;
 $('success-card').classList.toggle('hidden',!session.has_export||busy);$('result-mode').disabled=!session.has_export;
 document.querySelectorAll('.preset').forEach(b=>{b.classList.toggle('selected',b.dataset.preset===session.preset);b.disabled=busy;});
 $('suggestions').classList.toggle('hidden',session.messages.length>5||busy);document.querySelectorAll('.suggestions button').forEach(b=>b.disabled=busy);
 $('choose-folder').disabled=busy;
 if(lastJobStatus!==session.job.status&&session.job.status==='error')toast(session.job.error||'הפעולה לא הושלמה. נסו שוב.');
 if(lastJobStatus==='running'&&session.job.status==='complete'&&session.job.mode==='export')setMode(true);
 lastJobStatus=session.job.status;
 setVideo();renderChat();renderCues();applyCaption();
}
async function refresh(){if(!session||(typeof directBusy==='function'&&directBusy()))return;const id=session.id;try{const next=await api(`/api/session/${id}`);if(session&&session.id===id)applySession(next);}catch(e){toast(e.message);}}
async function loadSession(id){try{applySession(await api(`/api/session/${id}`));if(!poller)poller=setInterval(refresh,1200);}catch(e){toast(e.message);}}
async function importPath(path){try{toast('מכין את הסרטון שלך…');applySession(await api('/api/import',{path}));if(!poller)poller=setInterval(refresh,1200);$('toast').classList.add('hidden');}catch(e){toast(e.message);}}
async function upload(file){
 if(!file||!(/\.(mp4|mov)$/i.test(file.name))){toast('בחרו סרטון MP4 או MOV.');return;}
 if(desktop){const path=desktop.pathForFile(file);if(path){await importPath(path);return;}}
 try{toast('מכין את הסרטון שלך…');const r=await fetch('/api/upload',{method:'POST',headers:{'X-One-Token':token,'X-Filename':encodeURIComponent(file.name)},body:file});const out=await r.json();if(!r.ok)throw new Error(out.error);applySession(out);if(!poller)poller=setInterval(refresh,1200);$('toast').classList.add('hidden');}catch(e){toast(e.message);}
}
async function chooseVideo(){if(desktop){const path=await desktop.pickVideo();if(path)await importPath(path);}else $('file-input').click();}
async function mutate(route,data){
 if(chatPending||!session||(typeof directBusy==='function'&&directBusy()))return;const id=session.id;
 if(route==='/api/chat'){chatPending=true;applySession(session);}
try{const next=await api(route,{id,...data});if(session&&session.id===id){applySession(next);if(route==='/api/chat'&&next.chat_error&&!$('chat-input').value)$('chat-input').value=data.text;if(resultMode)setMode(false);}}catch(e){toast(e.message);if(route==='/api/chat'&&session&&session.id===id){if(!$('chat-input').value)$('chat-input').value=data.text;session.thinking=false;}}finally{chatPending=false;if(session)applySession(session);}}
$('choose-video').onclick=e=>{e.stopPropagation();chooseVideo();};$('drop-zone').onclick=chooseVideo;$('drop-zone').onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();chooseVideo();}};
$('file-input').onchange=e=>{upload(e.target.files[0]);e.target.value='';};
window.addEventListener('dragover',e=>{e.preventDefault();$('drop-zone').classList.add('dragover');});window.addEventListener('dragleave',e=>{if(!e.relatedTarget)$('drop-zone').classList.remove('dragover');});window.addEventListener('drop',e=>{e.preventDefault();$('drop-zone').classList.remove('dragover');upload(e.dataTransfer.files[0]);});
$('play').onclick=$('play-overlay').onclick=()=>{if(video.paused)video.play().catch(()=>toast('התצוגה עדיין בהכנה. נסו שוב בעוד רגע.'));else video.pause();};
video.addEventListener('play',()=>{$('play').textContent='Ⅱ';$('play-overlay').classList.add('hidden');});video.addEventListener('pause',()=>{$('play').textContent='▶';$('play-overlay').classList.toggle('hidden',!lastPreview);});
video.addEventListener('timeupdate',()=>{$('current-time').textContent=time(video.currentTime);$('seek').value=video.currentTime;applyCaption();});video.addEventListener('loadedmetadata',applyCaption);new ResizeObserver(applyCaption).observe($('video-container'));
$('seek').oninput=e=>{video.currentTime=Number(e.target.value);applyCaption();};$('mute').onclick=()=>{video.muted=!video.muted;$('mute').textContent=video.muted?'◖×':'◖))';};
$('source-mode').onclick=()=>setMode(false);$('result-mode').onclick=()=>setMode(true);
$('chat-form').onsubmit=async e=>{e.preventDefault();const text=$('chat-input').value.trim();if(!text||!session)return;$('chat-input').value='';await mutate('/api/chat',{text});};
$('chat-input').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('chat-form').requestSubmit();}};
 document.querySelectorAll('.suggestions button').forEach(b=>b.onclick=()=>mutate('/api/chat',{text:b.textContent}));document.querySelectorAll('.preset').forEach(b=>b.onclick=()=>mutate('/api/preset',{preset:b.dataset.preset}));
$('redo').onclick=()=>mutate('/api/redo',{});$('undo').onclick=()=>mutate('/api/undo',{});$('generate').onclick=()=>mutate('/api/transcribe',{});
function editCue(index){if(session.job.status==='running')return;editingIndex=index;const cue=session.cues[index];video.currentTime=cue.start;video.pause();applyCaption();$('edit-text').value=cue.lines.join('\n');$('edit-time').textContent=`${time(cue.start)} — ${time(cue.end)}`;$('edit-dialog').showModal();$('edit-text').focus();}
$('close-edit').onclick=$('cancel-edit').onclick=()=>$('edit-dialog').close();$('edit-form').onsubmit=async e=>{e.preventDefault();const text=$('edit-text').value.trim();if(!text)return;await mutate('/api/edit',{index:editingIndex,text});$('edit-dialog').close();};
$('choose-folder').onclick=async()=>{if(!desktop){toast('בחירת תיקייה זמינה באפליקציית ONE Captions.');return;}const name=await desktop.pickFolder();if(name)$('folder-name').textContent=name;};
$('export-button').onclick=async()=>{if(!desktop){toast('פתחו את אפליקציית ONE Captions כדי לבחור היכן לשמור את הסרטון.');return;}const target=await desktop.exportTarget(session.name);if(target)await mutate('/api/export',{target});};
$('open-result').onclick=()=>desktop?desktop.openExport(session.id):window.open(media('export'));$('reveal-result').onclick=()=>desktop?desktop.revealExport(session.id):toast('הצגת תיקייה זמינה באפליקציית ONE Captions.');
async function showHome(){if(typeof directBusy==='function'&&directBusy())return;if(typeof direct!=='undefined'){direct.selected=false;direct.word=null;direct.wordMode=false;updateDirect();}video.pause();if(poller){clearInterval(poller);poller=null;}session=null;$('workspace').classList.add('hidden');$('welcome').classList.remove('hidden');$('export-button').classList.add('hidden');$('undo').classList.add('hidden');$('redo').classList.add('hidden');$('home-button').classList.add('hidden');try{const sessions=await api('/api/sessions');$('recent-list').replaceChildren();const latest=sessions[0];if(latest){const b=document.createElement('button');b.className='recent-project';const img=document.createElement('img');img.className='recent-thumb';img.alt='תמונה מתוך הסרטון';img.loading='lazy';img.src=`/media/${latest.id}/thumbnail?token=${encodeURIComponent(token)}`;const detail=document.createElement('span');detail.className='recent-detail';const name=document.createElement('strong');name.textContent=latest.name;const edited=document.createElement('small');edited.textContent='נערך לאחרונה · '+new Intl.DateTimeFormat('he-IL',{dateStyle:'medium',timeStyle:'short'}).format(new Date(latest.updated*1000));detail.append(name,edited);b.append(img,detail);b.onclick=()=>loadSession(latest.id);$('recent-list').append(b);}$('recent').classList.toggle('hidden',!latest);}catch(e){toast(e.message);}}
$('home-button').onclick=showHome;
if(desktop){desktop.onSelectedVideo(importPath);if(navigator.platform.toLowerCase().includes('win'))$('reveal-result').textContent='הצג בתיקייה';}
window.addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='z'&&!['TEXTAREA','INPUT'].includes(document.activeElement.tagName)&&session){e.preventDefault();mutate(e.shiftKey?'/api/redo':'/api/undo',{});}});
showHome();
