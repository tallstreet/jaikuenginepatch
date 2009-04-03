var url = "http://devku.jaiku.com/feed/json";

// Create HTML
function show(json) {
	var c = document.getElementById("jaikus");
    var uls = c.getElementsByTagName("ul");
	if (!uls.length)
	    var ul = document.createElement("ul");
	else
	    var ul = uls[0];
	
	for (var i=json.stream.length-1; i >= 0; i--) {
	    var entry = json.stream[i];
		var id = "jaiku-" + entry.id;
	    if (!document.getElementById(id)) {
			var li = document.createElement("li");
			li.id = id;
			if ( i % 2 == 0 ) li.className = "even";
        
            // User
			var user = document.createElement("a");
			user.setAttribute('href', entry.user.url);
			user.appendChild(document.createTextNode(entry.user.nick));
        
            // Entry link & title
			var post = document.createElement("a");
			post.setAttribute('href', entry.url);
			post.appendChild(document.createTextNode(entry.title));
        
		    li.appendChild(user);
		    li.appendChild(document.createTextNode(": "));
			li.appendChild(post);
			ul.insertBefore(li, ul.firstChild);
		}
	}
	c.appendChild(ul);
}

// Load JSON
function load(){
    var c = document.getElementById("jaikus");
    if (!c) return;

	var head = document.getElementsByTagName("head")[0];
	script = document.createElement("script");
	script.type = "text/javascript";
	script.src = url + "?callback=show";
	head.appendChild(script)
}

window.onload = load;
setInterval( load, 1000 * 30);