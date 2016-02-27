<?php
$cid=filter_input(INPUT_GET, 'cid', FILTER_SANITIZE_NUMBER_INT);
$bounds=file_get_contents("cset-$cid.bounds", FILE_USE_INCLUDE_PATH);
$bbox=explode(",",$bounds);
?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">

<head>
   <title>OpenStreetMap Difference Engine</title>
   <link rel="icon" href="/osm/favicon.png" type="image/png">
   <link href="/osm/styles.css" type="text/css" rel="stylesheet"/>
   <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
   <script src="/jquery-2.1.3/jquery.min.js"></script>
   <link rel="stylesheet" href="/leaflet-0.7.3/leaflet.css" />
   <script src="/leaflet-0.7.3/leaflet.js"></script>
   <script src="/osm/easy-button.js"></script>
<style>
html, body, #map {
  width: 100%;
  height: 100%;
  margin: 0;
}
#btncontainer {
  margin: 10px;
}
.josmicon {
  background-image: url(josm-icon.png);
  width: 24px;
  height: 25px;
  background-position: 50% 50%;
  background-repeat: no-repeat;
  display: block;
  padding: 1px;
}
.osmicon {
  background-image: url(osm-icon.png);
  width: 24px;
  height: 25px;
  background-position: 50% 50%;
  background-repeat: no-repeat;
  display: block;
  padding: 1px;
}
.leaflet-control-layers-toggle {
  background-image: url(layers.png);
  width: 26px;
  height: 26px;
  color:#000;
}
</style>
</head>

<body>
<div id="map">
</div>

<script type="text/javascript">
<?php echo "var jsonfile = '/osmt/cset-$cid.json';\nvar cid = '$cid';";?>

(function($)
{
  $(document).ready(function()
  {
    $.ajaxSetup( { cache: false });
    load_json();
  });
})(jQuery);

var tileUrl = 'http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
var tileUrlBw = 'http://{s}.tiles.wmflabs.org/bw-mapnik/{z}/{x}/{y}.png'
var osmAttrib='&copy <a href="http://openstreetmap.org">OpenStreetMap</a> contributors';

var  geodkUrl = 'http://osmtools.septima.dk/mapproxy/tiles/1.0.0/kortforsyningen_ortoforaar/EPSG3857/{z}/{x}/{y}.jpeg';
var geodkAttrib='&copy <a href="http://kortforsyningen.dk">Geodatastyrelsen Denmark</a>';

var osm =   new L.TileLayer(tileUrl, {minZoom: 6, maxZoom: 18, subdomains: ['a','b','c'], attribution: osmAttrib, opacity:0.4});
var osmbw = new L.TileLayer(tileUrlBw, {minZoom: 6, maxZoom: 18, subdomains: ['a','b','c'], attribution: osmAttrib, opacity:0.4});
var geodk = new L.TileLayer(geodkUrl, {minZoom: 6, maxZoom: 20, attribution: geodkAttrib, opacity:0.4});
var baseMaps = {
    "Mapnik": osm,
    "Mapnik BW": osmbw,
    "Geodatastyrelsen DK": geodk
};
var map = new L.Map('map', {'dragging' : true, 'zoomControl': false, 'doubleClickZoom': false, layers:[osm]})

L.control.layers(baseMaps).addTo(map);
//L.control.layers(baseMaps, overlayMaps).addTo(map);

map.attributionControl.setPrefix(''); // Dont show 'powered by..'
map.fitBounds(<?php echo "[[$bbox[0],$bbox[1]],[$bbox[2],$bbox[3]]]" ?>);

L.easyButton('josmicon', openInJOSM ,"Open in JOSM", map);
L.easyButton('osmicon', openOSM ,"Open changeset on openstreetmap.org", map);

function openInJOSM() {
  var mb = map.getBounds();
  var vbox = [mb.getSouth(), mb.getWest(), mb.getNorth(), mb.getEast()];
  var url = "http://127.0.0.1:8111/load_and_zoom?left="+vbox[1]+"&right="+vbox[3]+"&top="+vbox[2]+"&bottom="+vbox[0];
  var request = new XMLHttpRequest();
  request.open('GET', url, true);
  request.send();
}
function openOSM() {
  var url = "http://www.openstreetmap.org/changeset/"+cid;
  window.location = url;
}

var markers;

//load_json();

function styleFunc(feature) {
  return {
    weight: 4,
    opacity: 0.7,
    color: feature.properties.color,
    fillOpacity: 0.2
  };
}

function pointToLayer(feature, latlng) {
  return L.circleMarker(latlng, {
    radius: 2,
    fillColor: "#ff7800",
    color: "#000",
    weight: 0,
    opacity: 1,
    fillOpacity: 0.8
    });
}

var layerPopup;
function highlightFeature(e) {
    var layer = e.target;
    h = layer.feature.properties.meta;
    tag = layer.feature.properties.tag;
    var popbody = 'Action: '+layer.feature.properties.action;
    var ksum = {}
    for (var v in tag) {
        for (var k in tag[v]) {
            ksum[k] += 1;
	}
    }
    var kstate = {}
    for (var k in ksum) {
        console.log('ksum, k='+k);
	var first = undefined;
        for (var v in tag) {
            if (first==undefined) {
                first = tag[v][k];
            }
            if (tag[v][k]==undefined) {
                kstate[k] = "tagadded";
            } else if (tag[v][k]!=first) {
                kstate[k] = "tagchanged";
            }
        }
    }

    popbody += '<table><thead><th>version</th>';
    for (var v in tag) {
        popbody += '<th>' + v + '</th>';
    }
    popbody += '</thead><tbody>';
    for (var k in ksum) {
        console.log('k='+k+' kstate='+kstate[k]);
        if (ksum.hasOwnProperty(k)) {
            if (kstate[k]==undefined) {
                popbody += '<tr><td>' + k + '</td>';
            } else {
                popbody += '<tr class="'+kstate[k]+'"><td>' + k + '</td>';
            }
            for (var v in tag) {
          	console.log('v='+v);
		if (tag[v][k]!=undefined) {
                    popbody += '<td>' + tag[v][k] + '</td>';
		} else {
                    popbody += '<td class="undefined"></td>';
		}
	    }
            popbody += '</tr>';
        }
    }
    popbody += '</tbody></table>';
    if (layer.feature.properties.popupContent!=undefined) {
        popbody += layer.feature.properties.popupContent;
    }
    console.log('popbody='+popbody);

    //var coords = layer.feature.geometry.coordinates;
    //var swapped_coords = [coords[0][1], coords[0][0]];
    if (map) {
       layerPopup = L.popup({offset:new L.Point(0,-6), closeButton: false})
           //.setLatLng(swapped_coords)
           .setLatLng(e.latlng)
           .setContent(popbody)
           .openOn(map);
    }
}

function resetHighlight(e) {
    if (layerPopup && map) {
        map.closePopup(layerPopup);
        layerPopup = null;
    }
}

function onEachFeature(feature, layer) {
  layer.on({
    mouseover: highlightFeature,
    mouseout: resetHighlight,
    //click: gotoVisualDiffFeature
  });
}

function load_json(){
  $.ajax({
    datatype: "json",
    url: jsonfile,
    success: function(data) {
      markers = new L.geoJson(data, { style: styleFunc, onEachFeature: onEachFeature, pointToLayer: pointToLayer});
      markers.addTo(map);
    }
  }).error(function() {});
}
</script>
</body>
