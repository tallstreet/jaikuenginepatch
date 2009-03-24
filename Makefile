build : 
	python manage.py build_docs

deploy : build
	python manage.py update $(DEPLOY)


zip_all :
	# pass
	
api_docs :
	python manage.py build_docs

profile : $(PROF_DB_PNG)

test :
	python manage.py test

clean :
	python manage.py clean
