#/bin/sh
jpgfile=$1
bmpfile=${jpgfile/%jpg/bmp}
mbmfile=${jpgfile/%jpg/mbm}
jpegtopnm < $jpgfile | ppmtobmp > $bmpfile
bmconv $mbmfile /c24$bmpfile
rm $bmpfile
