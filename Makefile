ZIPFILES=atom.zip beautifulsoup.zip django.zip gdata.zip \
				 oauth.zip simplejson.zip
ZIPDIRS := $(ZIPFILES:%.zip=%)
DOCSTXT := $(wildcard doc/*.txt)
DOCSHTML := $(DOCSTXT:doc/%.txt=api/templates/built_%.html)

#ZIPDIRS=atom beautifulsoup django gdata oauth simplejson
PROF_DIR=profiling
PROF_DB_CSV=$(PROF_DIR)/prof_db.csv
PROF_DB_PNG=$(PROF_DIR)/prof_db.png

build : zip_all api_docs

deploy : build
	python	manage.py update $(DEPLOY)


zip_all : $(ZIPFILES)

# ensures zipfiles are remade if the 
# related dir is newer than the file
$(ZIPFILES) : $(ZIPDIRS)
	./bin/zipper.sh $@

api_docs : $(DOCSHTML)

$(DOCSHTML) : $(DOCSTXT)
	./bin/build_api_docs.sh

$(DOCSTXT) : doc/method_post.txt
	
doc/method_post.txt :	common/api.py
	python bin/generate_api_docs.py

profile : $(PROF_DB_PNG)

$(PROF_DB_PNG) : $(PROF_DB_CSV)
	./bin/profile_png.sh

$(PROF_DB_CSV) : PROFILING = --include_profile
$(PROF_DB_CSV) : test
	@echo "they told me that the classics never go out of style but, they do, they do,"
	@echo "somehow, baby, I ain't never thought that we'd do too"

test :
	python manage.py test $(PROFILING)

clean :
	rm -f $(ZIPFILES)
	rm -f profiling/prof_db.*
	rm -f api/templates/built_*.html
	rm -f doc/method_*.txt
	rm -f doc/deco_*.txt
	find . -name \*.pyc | xargs -n 100 rm
