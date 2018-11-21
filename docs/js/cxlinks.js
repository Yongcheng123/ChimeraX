/*
 * === UCSF ChimeraX Copyright ===
 * Copyright 2016 Regents of the University of California.
 * All rights reserved.  This software provided pursuant to a
 * license agreement containing restrictions on its disclosure,
 * duplication and use.  For details see:
 * http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
 * This notice must be embedded in or attached to all copies,
 * including partial copies, of the software or any revisions
 * or derivations thereof.
 * === UCSF ChimeraX Copyright ===
 */

window.onload = function() {
  cxlinks_base="http://www.rbvi.ucsf.edu/chimerax/docs/"
  if(!window.navigator.userAgent.includes("ChimeraX")){
    window.onclick = function(e){
      if(e.target.tagName.toLowerCase()!="a")
	return true;
      var url=e.target.getAttribute("href").toLowerCase();
      if(url.startsWith("help:")){
	window.location.href = cxlinks_base + url.substring(5);
	return false;
      }
      if(url.startsWith("cxcmd:")){
	alert("This link only works in a ChimeraX browser and would execute a command.");
	return false;
      }
      return true;
    }
    var ls=document.links;
    for(var i=0;i<ls.length;i++){
      var link=ls[i];
      var url=link.getAttribute("href").toLowerCase();
      if(url.startsWith("cxcmd:"))
	link.style.color="darkred";
    }
  }
};
