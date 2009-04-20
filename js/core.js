jQuery.fn.addHover = function() {
  return this.hover(
    function(){ jQuery(this).addClass("hover"); },
    function(){ jQuery(this).removeClass("hover"); }
  )
};

jQuery.fn.bubble = function(top, left) {
  var bubble = null;
  var body = null;
  var _created = false;
  
  this.each(
    function() {
      this._title = this.title;
      this.removeAttribute("title");
    }
  );
  
  this.hover(
    function() {
      if (!_created) {
        $(document.body).append("<div id=\"status-bubble\"><div></div></div>");
        bubble = $("div#status-bubble");
        body = bubble.find("div");
        _created = true;
      }
      var offset = getOffset(this);
      var txt = $(this).find("div.bubble").html() || this._title.replace(",", "<br/>");
      
      body.html(txt);
      h = bubble.get(0).offsetHeight;
      bubble.css({
        top: (offset[1] + top - h + 10) + "px",
               left: (offset[0] + left - 120) + "px",
        visibility: "visible"
      });
    },
    function() {
      bubble.css("visibility", "hidden");
    }
  );
};

// Doesn't seem to work in firefox.
jQuery.fn.location = function () {
  var f = this;
  $("a#set-location").click(
    function () {
      $(this).parent().hide();
      f.show();
      $("input#loc", f)[0].focus();
      return false;
    }
  );
//  this.submit( function () {
//    $.ajax({
//      type: "POST",
//      url: this.action,
//      data: $("input", this).serialize(),
//      success: function(res){
//        var current = $("span#current-location");
//        if (current.length) {
//          var loc = $("input#loc").attr("value");
//          $("span#current-location").html(loc);
//        }
//        else {
//          var l = $("a#set-location");
//          l.html("Change");
//          l.before("<span id=\"current-location\">" + $("input#loc").attr("value") + "</span> | ");
//        }
//      }});
//    f.hide();
//    $("a#set-location").parent().show();
//    $("span.loader", this).hide();
//    $("input[@type=submit]").show();
//    return false;
//  });
}

var counter = {
  el : null,
  button : null,
  target: null,
  re : new RegExp(/^\s*|\s*$/g),
  count: function () {
    var value = counter.el.value;
    var count = value.length;
    chars_left = 140 - count;
    if (chars_left >= 0) {
      if ($(counter.target.parentNode).is('.overlimit')) {
        $(counter.target.parentNode).removeClass("overlimit");
      }

      if (chars_left > 1) {
        str = (chars_left) + " characters left";
      }
      else if (chars_left > 0) {
        str = "1 character left";
      }
      else {
        str = "No characters left";
      }
    } else {
      if (!$(counter.target.parentNode).is('.overlimit')) {
        $(counter.target.parentNode).addClass("overlimit");
      }

      if (chars_left < -1) {
        str = -chars_left + " characters over limit";
      }
      else {
        str = "1 character over limit";
      }
    }
    var ok = (count > 0 && count < 141) && (value.replace(counter.re,"") != counter.el._value);
    counter.button.disabled = !ok;
    counter.target.nodeValue = str;
  }
};

jQuery.fn.presence = function() {
  var msg = $("textarea#message", this);
  var submit = $(this).find("input[@type=submit]");
  var interval = null;
  var el = this;

  submit.attr("disabled", true);

  // Init selectable icons
  this.icons();
  
  // Message input
  msg.get(0)._value = msg.attr("value");
  msg.one("focus", function () {
    this.value = "";
    $(this).css({color: "#000"});
  });
  msg.focus( function () {
    $(this).css({color: "#000"});
    counter.el = this;
    counter.button = submit.get(0);
    counter.target = $("p#counter").get(0).firstChild;
    interval = window.setInterval(counter.count, 500);
  });
  msg.blur( function () {
    if (interval)
      window.clearInterval(interval);
  });

  msg.keypress(function (e) {
    var key = e.which ? e.which : e.keyCode;
    if (key == 13) {
      el.submit();
      //e.preventDefault(); 
    }            
  });
  // TODO termie: turn this back on
  return;
  this.submit( function () {
    if (submit.attr("disabled")) {
      submit.show();
      $("span.loader", this).hide();
      submit.attr("disabled", true);
      return false;
    }

    // Get location
    var loc = $("input#loc");
    if (loc.length > 0)
      $("input#location").attr("value", loc.attr("value"));
    if (window.location.search.indexOf("?page") == 0) {
      return;
    }
    $.ajax({
      type: "POST",
      url: this.action,
      data: $("textarea, input, select", this).serialize(),
      success: function(res){
        var tmp = document.createElement("div");
        tmp.innerHTML = res;
        var item = $("li", tmp);
        item.css("display", "none");
        
        if (item.size() > 0) {
          var f = $("div#stream li.date:first");
          if (f.length) {
            $("div#stream li.date:first").after(item);
          }
          else {
            var ul = document.createElement("ul");
            ul.className = "stream";
            $("div#stream p:first").remove();
            $("div#stream").prepend(ul);
            $("div#stream ul").append(item);
          }
          item.toggle();
        } else {
          alert("Hmm. Something went wrong.")
        }
            submit.show();
            $("span.loader", this).hide();
        submit.attr("disabled", true);
      }});
    msg.get(0)._value = msg.attr("value");
    msg.get(0).blur();
    msg.css({color: "#ccc"});
    return false;
  });
};

jQuery.fn.spy = function () {
  var stream = this;
  var timer = window.setInterval(
    function() {
      $.get(window.location.href,
            function (res) {
              stream.find("ul").remove();
              stream.append(res);
            })
    }, 1000 * 30);
};

jQuery.fn.toggleable = function (other) {
  var other = other;
  var el = this;

  $("a[@href=#" + this.attr("id") + "]").click(
    function () {
      if (el.css("display") == "none") {
        if (other) $(other).hide();
        el.show();
      }
      else {
        if (other) $(other).show();
        el.hide();
      }
    }
  )
};

jQuery.fn.toggleSelection = function (elements, select) {
  var els = $(elements);
  this.click(
    function () {
      els.attr("checked", select ? true : false);
      return false;
    }
  );
};

jQuery.fn.icons = function () {
  var opener = $("a#add-icons", this);
  var container = null;
  var current = null;
  var el = this;

  // Show and hide 
  opener.toggle(
    function(){
      if (!container) {
        var html = ["<div id=\"form-icons\">"];
        $("option", el).each(
          function() {
            if (this.value != "") {
              html.push("<label for=\"icon-" + this.value + "\" title=\"" + this.title + "\">");
              html.push("<img src=\"" + this.id + "\" class=\"icon\" alt=\"" + this.text + "\" />");
              if (this.title != "")
                html.push("<h4> "+ this.title+" </h4>")
              html.push("</label>");
            }
          }
        );
        html.push("</div>");
        el.append(html.join(""));

        container = $("div#form-icons");
        $("textarea#message").before("<img id=\"current-photo\" class=\"icon\"/>");
        current = $("img#current-photo").hide();
        current.click(function () {opener.click()});
        $("label", container).click(
          function () {
            var val = $(this).attr("for").replace("icon-","");
            var title = this.title;
            var index = 0;

            $("select#icon>option").each( function (i) {
              if (this.value == val) index = i;
            });
            $("select#icon").get(0).selectedIndex = index;

            $("label", container).removeClass("selected");
            $(this).addClass("selected");

            current.attr("src", $(this).find("img").get(0).src);
            current.css({display: 'inline'});
            current.click();

            var msg = $("textarea#message");
            msg.css({width: '349px'})
            if (msg.size() > 0) {
              el = msg.get(0);
              if (el._first) {
                el.value = this.title;
                el._first = null;
              }
              el.focus();
            }
          }
        );
      }
      container.show();
      $(document.body).bind("click", function () { current.click();});
    }, function(){
      container.hide();
      $(document.body).unbind("click");
    }
  );
};

jQuery.fn.avatars = function () {
  var container = this;
  var current = $("img#current");
  var save = $("button[@type='submit']");

  $("label", container).click(
    function (e) {
      var src = $("img", this).attr("src");
      
      $("li", container).removeClass("selected");
      $(this).parent().addClass("selected");
      
      $(this).parent().find("input").get(0).checked = true;
      current.attr("src", src);
      save.attr("class", "active");
      e.preventDefault();
    }
  );
};

jQuery.fn.ajaxify = function () {
  this.click(
    function () {
      var el = $(this).parent();
      el.html("loading...");

      $.ajax({
        type: "GET",
        url: this.href,
        success: function(res) {
          el.html(res);
        }
      });

      return false;
    }
  );
};

jQuery.fn.confirm = function () {
  this.click(
    function () {
      this.href = this.href + "&confirm=1";
      return window.confirm("Are you sure you want to " + this.title.toLowerCase() + "?");
    }
  );
};

jQuery.fn.setAccordion = function () {
  var container = this;
  var links = container.find("li>a");
  container._current = null;
  links.click (
    function () {
      var open = this.hash.substring(1, this.hash.length);
      if (container._current == open) {
        $("div#" + container._current).removeClass("current");
        container.find("ul li").removeClass("current");
        container.removeClass("open"); 
        container._current = null;
        return false;
      }
      else if (container._current){
        $("div#" + container._current).removeClass("current");
      }
      $("div#" + open).addClass("current").find("input[@type='text'], input[@type='file'], textarea").get(0).focus();
      container.find("ul li").removeClass("current");
      $(this.parentNode).addClass("current");
      container._current = open;
      container.addClass("open");  
      return false;
    }
  );
};

jQuery.fn.toggleCheckbox = function () {
  var all = $(this.form).find("input[@name=" + this.attr("name") + "]");
  var el = this;
  this.click(
    function () {
      var checked = this.checked;
      all.each(function() {
        this.checked = false;
      });
      this.checked = checked ? true : false;
    }
  );
};

jQuery.fn.poll = function (frwd) {
  var current = window.location.href;
  var interval = window.setInterval(
    function () {
      $.ajax({
        type: "GET",
        url: current,
        dataType: "json",
        success: function(res) {
          if (res.result)
            if (frwd)
              window.location.href = frwd;
          else 
            window.location.reload();
        }
      });
    }, 2500);
};

jQuery.fn.setTabs = function () {
  var container = this;
  var tabs = container.find("li>a");
  tabs.click(
    function () {
      var tab = this.hash.substring(1, this.hash.length);
      $("div#" + container._current).removeClass("current");
      $("div#" + tab).addClass("current");
      container.find("ul li").removeClass("current");
      $(this.parentNode).addClass("current");
      container._current = tab;
      return false;
    }
  );
  container._current = this.find("div.current").attr("id");
};

jQuery.fn.forms = function () {
  var btn = $("input[@type=submit]", this);
  btn.parent().prepend("<span class=\"loader\" title=\"Sending...\">&nbsp;</span>");
  
  this.bind("submit",
            function() {
              $("input[@type=submit]", this).hide();
              $("span.cancel", this).hide();
              $("span.loader", this).show();
            }
           );
  
  this.each(
    function() {
      // Some special cases
      switch (this.id) {
      case "comment-form":
        $("#participant-nicks > a", this).each( function (i) {
          $(this).click(
            function () {
              var nick = $(this).text();
              var textarea = $("#comment");
              var text = textarea.val();

              // get comment textarea selection
              var selection;
              textarea.focus();
              if(textarea.get(0).selectionStart == undefined) {
                var range = document.selection.createRange();
                selection = new Array(range.start, range.end);
              } else {
                selection = new Array(textarea.get(0).selectionStart,
                                textarea.get(0).selectionEnd);
              }

              // Cursor is at the beginning or selection includes the first
              // position?
              if(selection[0] === 0) {
                // Insert '@nickname: '
                textarea.val('@' + nick + ': ' +
                             text.substring(selection[1], text.length));
              } else {
                // Insert '@nickname'
                textarea.val(text.substring(0, selection[0]) +
                             '@' + nick +
                             text.substring(selection[1], text.length));
              }
              return false;
            }
          );
        });
        $("#participant-nicks").show();
        break;
      case "loginform":
        $("input[@type=text]", this).get(0).focus();
        break;
      case "signup":
        $("input[@type=text]", this).get(0).focus();
        var pwd = $("input#password");
        pwd.parent().append("<div id=\"pwstatus\"></div");
        pwd.bind("keyup", function () {
          analyseAccountPassword();
        });
        break;
      case "form-location":
        $(this).location();
        break;
      case "form-avatar":
        $("div.avatars", this).avatars();
        var a = $("a#toggle");
        if (a.size() > 0) {
          $("div.form-fields").hide();
          $("a#toggle").click(
            function () {
              $("div#account-form div.form-fields").show();
              $(this).hide();
              return false;
            }
          );
        }
        break;
      }

      switch (this.parentNode.id) {
      case "form-message":
        $(this).presence();
        break;
      }
    }
  );
};

$(document).ready(function() {
  // Main navigation hovers for IE
  if ( jQuery.browser.msie)
    $("ul#main-nav>li").addHover();
  
  var body = document.body;
  var bg = $(body).css("background-color");
  var mobile = ((bg == "#ffffff") || (bg == "rbg(255,255,255)"));
  
  if (!mobile) {
    // Common forms stuff
    $("form").forms();

    // Bubbles
    var sb = $("div#sidebar");
    if (sb.length)
      sb.find("div#contacts>ul>li").bubble(0, -18);

    // Delete confirmation links
    $("a.confirm-delete").confirm();
    // Spam confirmation links
    $("a.confirm-spam").confirm();

    // Ajaxified links
    $("a.ajaxify").ajaxify();

    $("div.tabs").setTabs();
    
    $("div.accordion").setTabs();
    
    $("form#change-number").toggleable("div#activation, div#activated");

    if (body.id == "welcome" || body.id == "contacts") {
      $("a#select-all").toggleSelection("input[@name='actor[]'], input[@name='email[]']", true);
      $("a#select-none").toggleSelection("input[@name='actor[]'], input[@name='email[]']", false);
    }
    
    if (body.id == "settings" && $("ul#badges").length) {
      initBadges();
    }    

    // Delete confirmation links
    $("input#only-channel, input#only-user").toggleCheckbox();
    
    //            if (body.id == "overview")
    //                $("div#stream").spy();
  }
});

/* Helper */

if (!Array.prototype.indexOf) {
  Array.prototype.indexOf = function (obj, fromIndex) {
    if (fromIndex == null) {
      fromIndex = 0;
    } else if (fromIndex < 0) {
      fromIndex = Math.max(0, this.length + fromIndex);
    }
    for (var i = fromIndex; i < this.length; i++) {
      if (this[i] === obj)
        return i;
    }
    return -1;
  };
}

/* Some old stuff */

var pwMinLen = 6;
var pwOkLen = 8;
var pwCut = 10;

function passwordStrength(pw, bans) {
  var points = 0;
  if(pw.length > 0) {
    if(pw.length >= pwMinLen) {
      pw = pw.substr(0, pwCut);
      var tpw = pw.toLowerCase();

      points = 1;
      var banned = false;
      for(var i = 0; i < bans.length; i++) {
        if(tpw.indexOf(bans[i].substr(0, pwCut).toLowerCase()) != -1) {
          banned = true;
          break;
        }
      }
      
      if(!banned) {
        if(pw.length >= pwOkLen) {
          points++;
        }
        if(pw.toLowerCase() != pw && pw.toUpperCase() != pw) {
          points++;
        }
        if(pw.search(/[0-9]/) != -1 && pw.search(/[A-Za-z]/) != -1) {
          points++;
        }
        if(pw.search(/[^0-9A-Za-z]/) != -1) {
          points++;
        }
        if(points > 4) {
          points = 4;
        }
      }
    }
  }
  else {
    points = -1;
  }
  return points;
}

function analyseAccountPassword(ret) {
  var pw = document.getElementById("password").value;
  var pwstatus = document.getElementById("pwstatus");
  if(pwstatus || ret) {
    ban = new Array();
    var tmp = document.getElementById("nick");
    if(tmp && tmp.value) {
      ban.push(tmp.value);
    }
    tmp = document.getElementById("email");
    if(tmp && tmp.value) {
      ban.push(tmp.value);
    }
    tmp = document.getElementById("first_name");
    if(tmp && tmp.value) {
      ban.push(tmp.value);
    }
    tmp = document.getElementById("last_name");
    if(tmp && tmp.value) {
      ban.push(tmp.value);
    }
    tmp = document.getElementById('city');
    if(tmp && tmp.value) {
      ban.push(tmp.value);
    }

    var points = passwordStrength(pw, ban);
    pwstatus.style.backgroundPosition = '0px ' + ((-points * 20) - 20)+ 'px';
    if(ret) {
      return points;
    }
  }
}

function checkPassword(pw) {
  if(pw.length < 8) {
    return false;
  }
  if(pw.search(/[A-Z]/) == -1) {
    return false;
  }
  if(pw.search(/[a-z]/) == -1) {
    return false;
  }
  if(pw.search(/[0-9]/) == -1) {
    return false;
  }
  return true;
}


function getFieldValue(id) {
  var field = document.getElementById(id);
  if(field && field.value) {
    return field.value;
  }
  return '';
}

function getOffset(o) {
  var top = 0, left = 0;
  while (o.offsetParent) {
    top += o.offsetTop  || 0;
    left += o.offsetLeft || 0;
    o = o.offsetParent;
  };
  return [left, top];
}
