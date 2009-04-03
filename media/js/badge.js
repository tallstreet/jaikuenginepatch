var COLORS = {
    white : {
        bkgcolor: "", gradientcolor1: "", hilitegradientcolor1: "", gradientcolor2: "",
        hilitegradientcolor2: "", bordercolor: "", hilitebordercolor: "", fontcolor: "",
        bubbletexthilite: "", timecolor: "", titlecolor: "", titlehilitecolor: "",
        descriptioncolor: "", descriptionhilitecolor: "", arrowcolor1: "", arrowhilitecolor1: "",
        arrowcolor2: "", arrowhilitecolor2: "", arrowbordercolor: "", arrowhilitebordercolor: "",
        mapcolor: "", maptextcolor: ""
    },
    red : {
        bkgcolor: "#F62817", gradientcolor1: "#C11B17", hilitegradientcolor1: "#ffffff", gradientcolor2: "#800517",
        hilitegradientcolor2: "#FFCCCC", bordercolor: "#C11B17", hilitebordercolor: "#FFCCFF", fontcolor: "#ffffff",
        bubbletexthilite: "#800517", timecolor: "#FF9966", titlecolor: "#800517", titlehilitecolor: "#800517",
        descriptioncolor: "#800517", descriptionhilitecolor: "#800517", arrowcolor1: "#F62817", arrowhilitecolor1: "#800517",
        arrowcolor2: "#800517", arrowhilitecolor2: "#F62817", arrowbordercolor: "#800517", arrowhilitebordercolor: "#800517",
        mapcolor: "#CC0000", maptextcolor: "#660000"
    },
    black : {
        bkgcolor: "#000000",gradientcolor1: "#222222",hilitegradientcolor1: "#ffffff",gradientcolor2: "#000000",
        hilitegradientcolor2: "#e1e1e1",bordercolor: "#333333",hilitebordercolor: "#C7E5E9",fontcolor: "#ffffff",
        bubbletexthilite: "#000000",timecolor: "#cccccc",titlecolor: "#cccccc",titlehilitecolor: "#ffffff",
        descriptioncolor: "#cccccc",descriptionhilitecolor: "#ffffff",arrowcolor1: "#000000",arrowhilitecolor1: "#ffffff",
        arrowcolor2: "#ffffff",arrowhilitecolor2: "#000000",arrowbordercolor: "#ffffff",arrowhilitebordercolor: "#ffffff",
        mapcolor: "#66CC33",maptextcolor: "#ffffff"
    },
    yellow : {
        bkgcolor: "#FFFF00",gradientcolor1: "#FF9900",hilitegradientcolor1: "#ffffff",gradientcolor2: "#FF6600",
        hilitegradientcolor2: "#FFFF99",bordercolor: "#FF9900",hilitebordercolor: "#FFFF99",fontcolor: "#ffffff",
        bubbletexthilite: "#000000",timecolor: "#993300",titlecolor: "#993300",titlehilitecolor: "#990000",
        descriptioncolor: "#993300",descriptionhilitecolor: "#990000",arrowcolor1: "#FFFF00",arrowhilitecolor1: "#993300",
        arrowcolor2: "#990000",arrowhilitecolor2: "#ffff00",arrowbordercolor: "#990000",arrowhilitebordercolor: "#990000",
        mapcolor: "#FFCC00",maptextcolor: "#993300"
    },
    green : {
        bkgcolor: "#336600",gradientcolor1: "#66CC33",hilitegradientcolor1: "#ffffff",gradientcolor2: "#669933",
        hilitegradientcolor2: "#CCFF99",bordercolor: "#66CC33",hilitebordercolor: "#CCFF99",fontcolor: "#ffffff",
        bubbletexthilite: "#000000",timecolor: "#006600",titlecolor: "#CCFF99",titlehilitecolor: "#ffffff",
        descriptioncolor: "#CCFF99",descriptionhilitecolor: "#ffffff",arrowcolor1: "#336600",arrowhilitecolor1: "#CCFF99",
        arrowcolor2: "#CCFF99",arrowhilitecolor2: "#336600",arrowbordercolor: "#CCFF99",arrowhilitebordercolor: "#CCFF99",
        mapcolor: "#66CC00",maptextcolor: "#ffffff"
    },
    pink : {
        bkgcolor: "#FF66FF",gradientcolor1: "#FF00CC",hilitegradientcolor1: "#ffffff",gradientcolor2: "#CC33CC",
        hilitegradientcolor2: "#FFCCFF",bordercolor: "#FF00CC",hilitebordercolor: "#FFCCFF",fontcolor: "#ffffff",
        bubbletexthilite: "#660066",timecolor: "#FFCCFF",titlecolor: "#CC0099",titlehilitecolor: "#990099",
        descriptioncolor: "#CC0099",descriptionhilitecolor: "#990099",arrowcolor1: "#FF66FF",arrowhilitecolor1: "#CC0099",
        arrowcolor2: "#CC0099",arrowhilitecolor2: "#FF66FF",arrowbordercolor: "#CC0099",arrowhilitebordercolor: "#CC0099",
        mapcolor: "#FF00CC",maptextcolor: "#CC0099"
    },
    blue : {
        bkgcolor: "#000066",gradientcolor1: "#0066CC",hilitegradientcolor1: "#ffffff",gradientcolor2: "#003399",
        hilitegradientcolor2: "#99CCCC",bordercolor: "#0066CC",hilitebordercolor: "#99CCCC",fontcolor: "#ffffff",
        bubbletexthilite: "#000066",timecolor: "#99CCCC",titlecolor: "#99CCCC",titlehilitecolor: "#ffffff",
        descriptioncolor: "#99CCCC",descriptionhilitecolor: "#ffffff",arrowcolor1: "#000066",arrowhilitecolor1: "#99CCCC",
        arrowcolor2: "#99CCCC",arrowhilitecolor2: "#000066",arrowbordercolor: "#99CCCC",arrowhilitebordercolor: "#99CCCC",
        mapcolor: "#336699",maptextcolor: "#99CCCC"
    },
    turqoise : {
        bkgcolor: "#BDEDFF",gradientcolor1: "#ffffff",hilitegradientcolor1: "#3399CC",gradientcolor2: "#E3E4FA",
        hilitegradientcolor2: "#336699",bordercolor: "#E3E4FA",hilitebordercolor: "#3399CC",fontcolor: "#003366",
        bubbletexthilite: "#ffffff",timecolor: "#003366",titlecolor: "#3399CC",titlehilitecolor: "#003366",
        descriptioncolor: "#3399CC",descriptionhilitecolor: "#003366",arrowcolor1: "#BDEDFF",arrowhilitecolor1: "#336699",
        arrowcolor2: "#336699",arrowhilitecolor2: "#BDEDFF",arrowbordercolor: "#336699",arrowhilitebordercolor: "#336699",
        mapcolor: "#66CCFF",maptextcolor: "#336699"
    }
};

jQuery.fn.badge = function () {
    var b = this.get(0);
    if (typeof b.SetVariable == "undefined")
        b = $("embed", this).get(0);
    
    var parent = this.parent().parent();
    var inputs = (parent.attr("id") == "badge-map") ? $("input.badge-color") : $("tr[@class != 'map-only'] input.badge-color");
    inputs.each( function() {
        b.SetVariable(this.name, this.value);
    });
    b.GotoFrame(0);
    b.Play();

    var s = inputs.serialize().replace(/&/g, "&amp;");
    var txt = parent.find("textarea");
    var code = txt.attr("value");
    txt.attr("value", code.replace(/\/feed\/badge(&(amp;)?(\w)*=%23(\w)*)*\"/g, "/feed/badge&amp;" + s + "\""));
}

function _showSubmit() {
    $("form#badge-config input[@type='submit']").show();
}

function initBadges() {
    $("a.show-config").toggle(function () {
        var parent = $(this).parent().parent();
        $("form#badge-config").insertAfter(parent.find("p.settings")).show();
        if (parent.attr("id") == "badge-map") {
            $("form#badge-config tr.map-only").show();
        } else {
            $("form#badge-config tr.map-only").hide();
        }
        return false;
    }, function () {
        $("form#badge-config").hide();
        return false;
    });

    $("textarea.badge-code").click(function () {
        this.focus();
        this.select();
    });


    $("form#badge-config").bind("submit", function (e) {
            $(this).parent().find("object").badge();
            window.setTimeout(_showSubmit, 100);
            return false;
        }
    );
        
    $("select.color-scheme").change(
        function () { 
            if (COLORS[this.value]) {
                var scheme = COLORS[this.value];
                sb = [];
                for (k in scheme) {
                    $("input[@name='" + k +"']").attr("value", scheme[k]); 
                }
                $(this).parent().parent().find("div>*").badge();
            }
        }
    );
}
 