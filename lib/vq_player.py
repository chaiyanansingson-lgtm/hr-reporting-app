# lib/vq_player.py — builds the self-contained interactive video-quiz player.
# Plays a YouTube or uploaded video; pauses and shows each question when the
# playhead reaches its timestamp; scores client-side and shows pass/fail.
import json


PLAYER_TMPL = r"""
<div style="font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif">
  <div id="vidbox" style="position:relative;border-radius:14px;overflow:hidden;
       background:#000;min-height:240px"></div>
  <div id="hud" style="margin-top:8px;font-size:13px;color:#5b6472"></div>
  <div id="overlay" style="display:none;margin-top:10px;border:1px solid #e6eaf1;
       border-radius:14px;padding:16px;background:#fff;
       box-shadow:0 10px 28px rgba(0,0,0,.10)"></div>
  <div id="result" style="display:none;margin-top:10px;border-radius:14px;
       padding:18px;text-align:center"></div>
</div>
<script src="https://www.youtube.com/iframe_api"></script>
<script>
var Q = __QUIZ__;
var score=0, maxscore=0, shown={}, finished=false, player=null, vid=null;
Q.questions.forEach(function(q){maxscore+=q.points;});
function esc(s){return (''+s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function fmt(t){t=Math.floor(t);return Math.floor(t/60)+':'+('0'+(t%60)).slice(-2);}
function hud(t){document.getElementById('hud').textContent='⏱ '+fmt(t)+'   •   คะแนน / score '+score+' / '+maxscore;}
function pause(){try{if(player&&player.pauseVideo)player.pauseVideo();}catch(e){} if(vid)vid.pause();}
function resume(){try{if(player&&player.playVideo)player.playVideo();}catch(e){} if(vid)vid.play();}
function checkTime(t){
  if(finished) return;
  for(var i=0;i<Q.questions.length;i++){
    if(!shown[i] && t>=Q.questions[i].t){ shown[i]=true; pause(); showQ(i); return; }
  }
}
function showQ(i){
  var q=Q.questions[i]; var o=document.getElementById('overlay'); o.style.display='block';
  var h='<div style="font-weight:700;margin-bottom:6px;color:#715091">❓ คำถาม · question (ที่ '+fmt(q.t)+')</div>';
  h+='<div style="margin-bottom:12px;font-size:15px">'+esc(q.prompt)+'</div>';
  if(q.qtype==='single'){ q.options.forEach(function(op,j){ h+='<label style="display:block;padding:6px 2px"><input type="radio" name="q" value="'+j+'"> '+esc(op)+'</label>'; }); }
  else if(q.qtype==='multiple'){ q.options.forEach(function(op,j){ h+='<label style="display:block;padding:6px 2px"><input type="checkbox" name="q" value="'+j+'"> '+esc(op)+'</label>'; }); h+='<div style="font-size:12px;color:#888;margin-top:4px">เลือกได้มากกว่า 1 / choose all that apply</div>'; }
  else if(q.qtype==='truefalse'){ [['true','True / จริง'],['false','False / เท็จ']].forEach(function(p){ h+='<label style="display:block;padding:6px 2px"><input type="radio" name="q" value="'+p[0]+'"> '+p[1]+'</label>'; }); }
  else { h+='<input id="shortans" type="text" style="width:100%;padding:9px;border:1px solid #ccc;border-radius:8px" placeholder="พิมพ์คำตอบ / your answer">'; }
  h+='<div id="qmsg" style="margin-top:8px;font-size:13px;min-height:18px"></div>';
  h+='<button id="qbtn" onclick="submitQ('+i+')" style="margin-top:6px;background:#009ADE;color:#fff;border:0;border-radius:10px;padding:10px 18px;font-weight:700;cursor:pointer">ส่งคำตอบ / Submit</button>';
  o.innerHTML=h;
}
function submitQ(i){
  var q=Q.questions[i]; var correct=false, answered=true;
  if(q.qtype==='single'){ var s=document.querySelector('input[name=q]:checked'); answered=!!s; if(s) correct=(parseInt(s.value)===q.correct); }
  else if(q.qtype==='multiple'){ var sel=[].slice.call(document.querySelectorAll('input[name=q]:checked')).map(function(e){return parseInt(e.value);}); var cor=q.correct||[]; answered=sel.length>0; correct=(sel.length===cor.length && sel.every(function(v){return cor.indexOf(v)>=0;})); }
  else if(q.qtype==='truefalse'){ var s2=document.querySelector('input[name=q]:checked'); answered=!!s2; if(s2) correct=((s2.value==='true')===(q.correct===true||q.correct==='true')); }
  else { var a=(document.getElementById('shortans').value||'').trim().toLowerCase(); answered=a.length>0; correct=(a===(''+q.correct).trim().toLowerCase()); }
  if(!answered){ document.getElementById('qmsg').innerHTML='<span style="color:#c0392b">กรุณาตอบก่อน / please answer</span>'; return; }
  if(correct) score+=q.points;
  var o=document.getElementById('overlay'); o.style.display='none'; o.innerHTML='';
  hud(0); resume();
}
function finish(){
  if(finished) return; finished=true;
  var pct = maxscore>0 ? Math.round(score/maxscore*100) : 100;
  var passed = pct >= Q.pass_pct;
  var r=document.getElementById('result'); r.style.display='block';
  r.style.background = passed ? '#e8f7ee' : '#fdeaea';
  r.innerHTML='<div style="font-size:34px">'+(passed?'✅':'❌')+'</div>'+
    '<div style="font-size:20px;font-weight:800;margin:6px 0">'+(passed?'ผ่าน / Passed':'ไม่ผ่าน / Not passed')+'</div>'+
    '<div style="font-size:16px">คะแนน / Score: <b>'+score+' / '+maxscore+'</b> ('+pct+'%) • เกณฑ์ผ่าน / pass ≥ '+Q.pass_pct+'%</div>';
  document.getElementById('overlay').style.display='none';
}
if(Q.video_type==='youtube'){
  var d=document.createElement('div'); d.id='ytp'; document.getElementById('vidbox').appendChild(d);
  window.onYouTubeIframeAPIReady=function(){
    player=new YT.Player('ytp',{height:'400',width:'100%',videoId:Q.youtube_id,
      playerVars:{rel:0,modestbranding:1},
      events:{onReady:function(){ setInterval(function(){ try{ if(player.getPlayerState&&player.getPlayerState()===1){ var t=player.getCurrentTime(); hud(t); checkTime(t); } }catch(e){} },400); },
               onStateChange:function(e){ if(e.data===0){ finish(); } }}});
  };
  if(window.YT && window.YT.Player){ window.onYouTubeIframeAPIReady(); }
} else {
  vid=document.createElement('video'); vid.id='vidp'; vid.controls=true;
  vid.style.width='100%'; vid.style.maxHeight='430px'; vid.src=Q.video_src;
  document.getElementById('vidbox').appendChild(vid);
  vid.addEventListener('timeupdate',function(){ hud(vid.currentTime); checkTime(vid.currentTime); });
  vid.addEventListener('ended',function(){ finish(); });
}
</script>
"""


def build_player(course, qs):
    quiz = {
        "video_type": course.get("video_type") or "youtube",
        "youtube_id": course.get("youtube_id") or "",
        "video_src": (f"data:{course.get('video_mime') or 'video/mp4'};base64,"
                      f"{course.get('video_data')}"
                      if course.get("video_data") else ""),
        "pass_pct": float(course.get("pass_pct") or 70),
        "questions": [{"t": int(q["t_seconds"]), "qtype": q["qtype"],
                       "prompt": q["prompt"], "options": q["options"],
                       "correct": q["correct"], "points": q["points"]}
                      for q in qs],
    }
    blob = json.dumps(quiz).replace("</", "<\\/")
    return PLAYER_TMPL.replace("__QUIZ__", blob)
