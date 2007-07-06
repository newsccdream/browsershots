def preload_foreign_keys(instances, **kwargs):
    """
    Preload the object cache for some foreign key fields.

    Use this if you have a set of books and you want to avoid a new
    database query for each author when you display them.
    >>> preload_foreign_keys(books, author=True)

    You can preload more than one field, and nested foreign keys:
    >>> preload_foreign_keys(books, author=True, publisher=True)
    >>> preload_foreign_keys(books, publisher__city=True)

    The following examples are equivalent. Use the second form if you
    already have the list of authors:
    >>> preload_foreign_keys(books, author=True)
    >>> preload_foreign_keys(books, author=Author.objects.filter(
            id__in=set([book.author_id for book in books])))
    """
    if not len(instances):
        return # Nothing to do.
    fieldnames = kwargs.keys()
    fieldnames.sort() # Process short names before nested names.
    for fieldname in fieldnames:
        if '__' in fieldname:
            firstpart, rest = fieldname.split('__', 1)
            field = instances[0]._meta.get_field(firstpart)
            field_cache = field.get_cache_name()
            # Get values of foreign keys from the cache.
            values = []
            for instance in instances:
                if not hasattr(instance, field_cache):
                    # Preload cache if necessary.
                    preload_foreign_keys(instances, **{firstpart: True})
                value = getattr(instance, field_cache)
                if value not in values:
                    values.append(value)
            # Recursive call to preload nested foreign keys.
            preload_foreign_keys(values, **{rest: kwargs[fieldname]})
        else:
            field = instances[0]._meta.get_field(fieldname)
            field_id = fieldname + '_id'
            field_cache = field.get_cache_name()
            values = kwargs[fieldname]
            if values is True:
                # Load needed values from database with just one SQL query.
                ids = [getattr(instance, field_id) for instance in instances]
                values = field.rel.to.objects.filter(id__in=set(ids))
            # Fill the foreign key cache.
            value_dict = dict([(value.id, value) for value in values])
            for instance in instances:
                value_id = getattr(instance, field_id)
                if value_id in value_dict:
                    setattr(instance, field_cache, value_dict[value_id])