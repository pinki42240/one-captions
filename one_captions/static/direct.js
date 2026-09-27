'use strict';
// Drafts paint locally. One pointer release commits through the same executor as chat.
const direct={selected:false,word:null,wordMode:false,active:null,pending:false,snap:true};
const frame=$('video-container');
frame.insertAdjacentHTML('beforeend','<div id="direct-safe" class="direct-safe hidden"></div><div id="direct-v" class="direct-guide vertical hidden"></div><div id="direct-h" class="direct-guide horizontal hidden"></div><div id="direct-box" class="direct-box hidden"><button type="button" class="resize-handle" id="direct-resize" aria-label="שינוי גודל כתוביות"></button></div>');
$('video-stage').nextElementSibling.insertAdjacentHTML('afterend',`<section id="direct-controls" class="direct-controls hidden" aria-label="עיצוב כתוביות בפריים"><div class="direct-heading"><strong id="direct-title">כל הכתוביות</strong><button type="button" id="direct-all">כל הכתוביות</button><button type="button" id="direct-word">בחירת מילה</button><button type="button" id="direct-snap">Snap ✓</button><button type="button" id="direct-close" aria-label="סגירת עריכת כתוביות">×</button></div><div class="direct-row"><label>גודל <input id="direct-font" type="range" step="1" aria-label="גודל פונט"><output id="direct-font-value"></output></label><button type="button" id="direct-bold" aria-label="מודגש"><b>B</b></button><button type="button" id="direct-underline" aria-label="קו תחתון"><u>U</u></button><button type="button" id="direct-italic" aria-label="נטוי"><i>I</i></button><label>צבע <input type="color" id="direct-color" aria-label="צבע כתוביות"></label></div><div class="direct-row"><label>מתאר <input id="direct-outline" type="range" min="0" max="15" step=".1" aria-label="עובי מתאר"><output id="direct-outline-value"></output></label><label>צל <input id="direct-shadow" type="range" min="0" max="5" step=".1" aria-label="עוצמת צל"><output id="direct-shadow-value"></output></label><label>זוהר <input id="direct-glow" type="range" min="0" max="15" step=".1" aria-label="עוצמת זוהר"><output id="direct-glow-value"></output></label></div><div class="direct-hint">גררו את הכתוביות להזזה · גררו את הידית לשינוי גודל · לחיצה כפולה לבחירת מילה · Alt מבטל Snap זמנית</div></section>`);
document.querySelector('.style-section').append($('direct-controls'));
function directBusy(){return Boolean(direct.active||direct.pending);}
function directWordSpan(){return [...$('caption-overlay').querySelectorAll('[data-word]')].find(s=>direct.word&&normalize(s.dataset.word)===normalize(direct.word.word)&&Number(s.dataset.occurrence)===direct.word.occurrence);}
function directBounds(){
 if(direct.word){const span=directWordSpan();if(span)return span.getBoundingClientRect();}
 const range=document.createRange();range.selectNodeContents($('caption-overlay'));return range.getBoundingClientRect();
}
function directValues(){
 const s=session.settings,base=session.width*s.font_size_ratio;
 const span=directWordSpan(),st=direct.word&&span?session.word_runs?.[Number(span.dataset.cue)]?.[Number(span.dataset.token)]||{}:{};
 return {font:(st.font_size||base)*(st.scale||1),bold:st.bold??s.bold,underline:st.underline??s.underline??false,italic:st.italic??s.italic??false,color:st.color||colorFromASS(s.primary_color),outline:st.outline??base*s.outline_ratio,shadow:st.shadow??s.shadow??0,glow:st.glow??s.glow??0};
}
function updateDirect(){
 const visible=Boolean(session&&direct.selected&&!resultMode&&$('caption-overlay').textContent&&(!direct.word||directWordSpan()));
 $('direct-controls').classList.toggle('hidden',!visible);$('direct-box').classList.toggle('hidden',!visible);$('direct-safe').classList.toggle('hidden',!visible);
 if(!visible){$('direct-v').classList.add('hidden');$('direct-h').classList.add('hidden');return;}
 const box=directBounds(),f=frame.getBoundingClientRect();Object.assign($('direct-box').style,{left:(box.left-f.left)+'px',top:(box.top-f.top)+'px',width:box.width+'px',height:box.height+'px'});
 $('direct-title').textContent=direct.word?'״'+direct.word.word+'״ · הופעה '+direct.word.occurrence:direct.wordMode?'לחצו על מילה בפריים':'כל הכתוביות';
 $('direct-word').classList.toggle('active',direct.wordMode);$('direct-all').classList.toggle('active',!direct.wordMode);$('direct-snap').classList.toggle('active',direct.snap);
 const v=directValues();$('direct-shadow').step=direct.word?'.1':'1';$('direct-word').disabled=!session.has_captions;$('direct-font').min=direct.word?16:Math.ceil(session.width*.025);$('direct-font').max=direct.word?250:Math.floor(session.width*.12);$('direct-font').value=v.font;$('direct-font-value').textContent=Math.round(v.font);$('direct-color').value=v.color;
 for(const key of ['bold','underline','italic']){$('direct-'+key).classList.toggle('active',Boolean(v[key]));$('direct-'+key).setAttribute('aria-pressed',String(Boolean(v[key])));}
 for(const key of ['outline','shadow','glow']){$('direct-'+key).max=key==='outline'&&!direct.word?Math.min(15,session.width*session.settings.font_size_ratio*.15):key==='shadow'?(direct.word?10:5):15;$('direct-'+key).value=v[key];$('direct-'+key+'-value').textContent=Number(v[key]).toFixed(1).replace('.0','');}
 document.querySelectorAll('#direct-controls input,#direct-controls button,#direct-resize').forEach(el=>el.disabled=direct.pending||session.thinking||session.job.status==='running'||(el.id==='direct-word'&&!session.has_captions));
}
function selectDirect(word=null){if(!session||resultMode||directBusy()||session.thinking||session.job.status==='running')return;direct.selected=true;direct.word=word;direct.wordMode=Boolean(word);video.pause();if(word)applyCaption();else updateDirect();}
function directSelectWord(span){if(!span?.dataset.word||Number(span.dataset.cue)<0)return;selectDirect({word:span.dataset.word,occurrence:Number(span.dataset.occurrence)});}
function directBlockUI(){const busy=directBusy()||chatPending||session.thinking||session.job.status==='running';for(const el of document.querySelectorAll('#chat-input,.send-btn,#generate,.preset,#choose-folder'))el.disabled=busy;$('undo').disabled=busy||!session.can_undo;$('redo').disabled=busy||!session.can_redo;$('export-button').disabled=busy||!session.has_captions;}
function startDirect(kind,e){
 if(!session||resultMode||directBusy()||chatPending||session.thinking||session.job.status==='running')return false;
 video.pause();direct.selected=true;const f=frame.getBoundingClientRect(),box=directBounds();direct.active={kind,before:structuredClone(session),actions:[],x:e?.clientX,y:e?.clientY,frame:f,box,bottomOffset:(box.bottom-f.top)/f.height-(1-session.settings.bottom_margin_ratio),centerOffset:(box.left+box.width/2-f.left)/f.width-(session.settings.center_x_ratio??.5),font:directValues().font,id:e?.pointerId};
 directBlockUI();updateDirect();if(e?.pointerId!==undefined)frame.setPointerCapture(e.pointerId);return true;
}
function styleDraft(key,value){
 if(!direct.active)return;
 if(direct.word){
  const styles=key==='font'?{font_size:value,scale:1}:{[key]:value};const span=directWordSpan();if(!span)return;
  Object.assign(session.word_runs[Number(span.dataset.cue)][Number(span.dataset.token)],styles);
  direct.active.actions=[{op:'word_style',...direct.word,styles}];
 }else{
  const field={font:'font_size_ratio',color:'primary_color',outline:'outline_ratio'}[key]||key;
  const converted=key==='font'?value/session.width:key==='outline'?value/(session.width*session.settings.font_size_ratio):key==='color'?'&H00'+value.slice(5,7)+value.slice(3,5)+value.slice(1,3):value;
  session.settings[field]=converted;direct.active.actions=[{op:'set',field,value:key==='color'?value:converted}];
 }
 applyCaption();
}
async function finishDirect(cancel=false){
 const gesture=direct.active;if(!gesture)return;direct.active=null;$('direct-v').classList.add('hidden');$('direct-h').classList.add('hidden');
 if(gesture.id!==undefined&&frame.hasPointerCapture(gesture.id))frame.releasePointerCapture(gesture.id);
 if(cancel){applySession(gesture.before,true);return;}if(!gesture.actions.length){directBlockUI();updateDirect();return;}
 direct.pending=true;applySession(session,true);const id=gesture.before.id;
 try{const next=await api('/api/direct',{id,revision:gesture.before.revision,actions:gesture.actions,label:gesture.kind==='move'?'גרירת כתוביות':gesture.kind==='resize'?'שינוי גודל בפריים':'עיצוב ידני'});direct.pending=false;if(session?.id===id)applySession(next,true);}
 catch(e){direct.pending=false;if(session?.id===id){try{applySession(await api('/api/session/'+id),true);}catch{applySession(gesture.before,true);}toast(e.message);}}
 finally{direct.pending=false;if(session?.id===id)applySession(session,true);}
}
$('caption-overlay').addEventListener('pointerdown',e=>{
 if(e.button!==0||directBusy())return;e.preventDefault();
 const span=e.target.closest('[data-word]'),key=span?span.dataset.cue+':'+span.dataset.token:null,now=performance.now();
 if(direct.wordMode||(key&&direct.lastTap?.key===key&&now-direct.lastTap.time<350)){direct.lastTap=null;directSelectWord(span);return;}
 direct.lastTap={key,time:now};selectDirect();startDirect('move',e);
});
frame.addEventListener('dblclick',e=>{e.preventDefault();directSelectWord(document.elementFromPoint(e.clientX,e.clientY)?.closest('[data-word]'));});
$('direct-resize').addEventListener('pointerdown',e=>{e.preventDefault();e.stopPropagation();startDirect('resize',e);});
function nearest(value,candidates,threshold){let best=null;for(const c of candidates)if(Math.abs(c.value-value)<threshold&&(!best||Math.abs(c.value-value)<Math.abs(best.value-value)))best=c;return best;}
frame.addEventListener('pointermove',e=>{
 const g=direct.active;if(!g||g.id!==e.pointerId)return;e.preventDefault();
 if(g.kind==='resize'){
  const ratio=Math.max(.2,1+((e.clientX-g.x)+(e.clientY-g.y))/Math.max(40,g.box.width+g.box.height));const low=direct.word?16:session.width*.025,high=direct.word?250:session.width*.12;styleDraft('font',Math.min(high,Math.max(low,g.font*ratio)));return;
 }
 if(g.kind!=='move'||Math.hypot(e.clientX-g.x,e.clientY-g.y)<2)return;direct.lastTap=null;
 let x=(g.before.settings.center_x_ratio??.5)+(e.clientX-g.x)/g.frame.width,y=1-g.before.settings.bottom_margin_ratio+(e.clientY-g.y)/g.frame.height;
 const half=Math.min(.5,g.box.width/(2*g.frame.width)),h=Math.min(1,g.box.height/g.frame.height);let sx=null,sy=null;
 if(direct.snap&&!e.altKey){sx=nearest(x,[{value:.5-g.centerOffset,line:.5},{value:.1+half-g.centerOffset,line:.1},{value:.9-half-g.centerOffset,line:.9}],8/g.frame.width);sy=nearest(y,[... [.15,.5,.85].map(line=>({value:line+h/2-g.bottomOffset,line})),{value:.1+h-g.bottomOffset,line:.1},{value:.9-g.bottomOffset,line:.9}],8/g.frame.height);if(sx)x=sx.value;if(sy)y=sy.value;}
 x=Math.min(1,Math.max(0,Math.min(1-half-g.centerOffset,Math.max(half-g.centerOffset,x))));y=Math.min(1,Math.max(0,Math.min(1-g.bottomOffset,Math.max(h-g.bottomOffset,y))));session.settings.center_x_ratio=x;session.settings.bottom_margin_ratio=1-y;
 g.actions=[{op:'set',field:'center_x_ratio',value:x},{op:'set',field:'bottom_margin_ratio',value:1-y}];if(Math.abs(e.clientX-g.x)>Math.abs(e.clientY-g.y))g.actions.reverse();
 $('direct-v').classList.toggle('hidden',!sx);$('direct-h').classList.toggle('hidden',!sy);if(sx)$('direct-v').style.left=sx.line*100+'%';if(sy)$('direct-h').style.top=sy.line*100+'%';applyCaption();
});
frame.addEventListener('pointerup',e=>{if(direct.active?.id===e.pointerId)finishDirect();});frame.addEventListener('pointercancel',e=>{if(direct.active?.id===e.pointerId)finishDirect(true);});
for(const key of ['font','outline','shadow','glow','color']){
 const el=$('direct-'+key);el.addEventListener('input',()=>{const value=key==='color'?el.value:Number(el.value);if(!direct.active&&!startDirect('style'))return;styleDraft(key,value);});el.addEventListener('change',()=>finishDirect());
}
for(const key of ['bold','underline','italic'])$('direct-'+key).onclick=()=>{const value=!directValues()[key];if(startDirect('style')){styleDraft(key,value);finishDirect();}};
$('direct-word').onclick=()=>{direct.wordMode=true;direct.word=null;updateDirect();};$('direct-all').onclick=()=>{direct.wordMode=false;direct.word=null;applyCaption();};$('direct-snap').onclick=()=>{direct.snap=!direct.snap;updateDirect();};$('direct-close').onclick=()=>{direct.selected=false;direct.word=null;direct.wordMode=false;applyCaption();};
window.addEventListener('keydown',e=>{if(e.key==='Escape'){if(direct.active){e.preventDefault();finishDirect(true);}else{direct.selected=false;direct.word=null;direct.wordMode=false;applyCaption();}}});

frame.addEventListener('lostpointercapture',e=>{if(direct.active?.id===e.pointerId)finishDirect(true);});window.addEventListener('blur',()=>{if(direct.active?.id!==undefined)finishDirect(true);});
