function htimestamp(ts, now_txt, ago_txt) {
  var then = new Date(ts);
  var now = new Date();
  var secs = (now.getTime()-then.getTime())/1000;
  var mins = Math.floor(secs/60);
  var hrs = Math.floor(secs/60/60);
  var days = Math.floor(secs/60/60/24);
  if (mins<60) {
    if (mins==0) {
      if (now_txt)
        return now_txt;
      else
        return Math.trunc(secs)+"s"
    }
    if (mins==1) {
      txt = "1 minute";
      if (ago_txt)
        txt += " "+ago_txt;
      return txt;
    } else {
      txt = mins+" minutes";
      if (ago_txt)
        txt += " "+ago_txt;
      return txt;
    }
  } else if (then.getDate()==now.getDate()) {
    var hrstxt, mintxt;
    if (hrs==1) {
      hrstxt = "hour";
    } else {
      hrstxt = "hours";
    }
    var remmins = mins-hrs*60;
    if (remmins==1) {
      mintxt = "minute";
    } else {
      mintxt = "minutes";
    }
    if ((mins-hrs*60)==0) {
      txt = hrs+" "+hrstxt;
      if (ago_txt)
        txt += " "+ago_txt;
      return txt;
    } else {
      txt = hrs+" "+hrstxt+", "+remmins+" "+mintxt;
      if (ago_txt)
        txt += " "+ago_txt;
      return txt;
    }
  } else if (then.getDate()==now.getDate()-1 ||
		     (now.getDate()==1 && (then.getDate()!=now.getDate()))) {
    return "Yesterday "+then.toLocaleTimeString();
  }
  return then.toLocaleString();
}
