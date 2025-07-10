import yaml
from pathlib import Path

def to_camel_case(snake_str):
    components = snake_str.split('_')
    return "".join(x.title() for x in components)

def openapi_to_pydantic(schema_name, schema_def, all_schemas):
    class_name = to_camel_case(schema_name.replace("Aura", ""))
    if not class_name:
        class_name = schema_name

    fields = []
    imports = {"BaseModel"}
    custom_classes = set()

    if "allOf" in schema_def:
        parent_classes = []
        for item in schema_def["allOf"]:
            if "$ref" in item:
                ref_name = item["$ref"].split("/")[-1]
                parent_classes.append(to_camel_case(ref_name.replace("Aura", "")))
                imports.add(parent_classes[-1])
                custom_classes.add(parent_classes[-1])
            else:
                # Inline schema definition
                for prop_name, prop_def in item.get("properties", {}).items():
                    field_type, field_imports, field_custom_classes = get_pydantic_type(prop_def, all_schemas)
                    fields.append(f"    {prop_name}: {field_type}")
                    imports.update(field_imports)
                    custom_classes.update(field_custom_classes)
        
        model_str = f"class {class_name}({', '.join(parent_classes)}):\n"
        if not fields:
             model_str += "    pass\n"

    else:
        model_str = f"class {class_name}(BaseModel):\n"
        for prop_name, prop_def in schema_def.get("properties", {}).items():
            field_type, field_imports, field_custom_classes = get_pydantic_type(prop_def, all_schemas)
            fields.append(f"    {prop_name}: {field_type}")
            imports.update(field_imports)
            custom_classes.update(field_custom_classes)

    if fields:
        model_str += "\n".join(fields)
    elif "allOf" not in schema_def:
        model_str += "    pass"
        
    model_str += "\n\n"
    
    return model_str, imports, custom_classes

def get_pydantic_type(prop_def, all_schemas):
    imports = set()
    custom_classes = set()
    
    if "$ref" in prop_def:
        ref_name = prop_def["$ref"].split("/")[-1]
        type_name = to_camel_case(ref_name.replace("Aura", ""))
        imports.add(type_name)
        custom_classes.add(type_name)
        return type_name, imports, custom_classes

    prop_type = prop_def.get("type")
    nullable = prop_def.get("nullable", False)
    
    pydantic_type = "Any"
    
    if prop_type == "string":
        pydantic_type = "str"
    elif prop_type == "integer":
        pydantic_type = "int"
    elif prop_type == "number":
        pydantic_type = "float"
    elif prop_type == "boolean":
        pydantic_type = "bool"
    elif prop_type == "array":
        imports.add("List")
        items_def = prop_def.get("items", {})
        item_type, item_imports, item_custom_classes = get_pydantic_type(items_def, all_schemas)
        imports.update(item_imports)
        custom_classes.update(item_custom_classes)
        pydantic_type = f"List[{item_type}]"
    elif prop_type == "object":
         pydantic_type = "Dict[str, Any]"
         imports.add("Dict")
         imports.add("Any")

    if "anyOf" in prop_def:
        imports.add("Union")
        union_types = []
        for item in prop_def["anyOf"]:
            item_type, item_imports, item_custom_classes = get_pydantic_type(item, all_schemas)
            union_types.append(item_type)
            imports.update(item_imports)
            custom_classes.update(item_custom_classes)
        pydantic_type = f"Union[{', '.join(union_types)}]"


    if nullable:
        imports.add("Optional")
        pydantic_type = f"Optional[{pydantic_type}]"
        
    return pydantic_type, imports, custom_classes

def main():
    yaml_path = Path("aura_api_doc.yaml")
    output_path = Path("src/swapi_client/generated_models.py")

    with open(yaml_path, 'r') as f:
        spec = yaml.safe_load(f)

    schemas = spec.get("components", {}).get("schemas", {})
    
    all_models_code = ""
    all_imports = {"BaseModel"}
    all_custom_classes = set()

    model_defs = {}
    for schema_name, schema_def in schemas.items():
        if schema_name.endswith("Aura"):
            model_code, imports, custom_classes = openapi_to_pydantic(schema_name, schema_def, schemas)
            model_defs[to_camel_case(schema_name.replace("Aura", ""))] = model_code
            all_imports.update(imports)
            all_custom_classes.update(custom_classes)

    # Basic topological sort
    sorted_classes = []
    while len(sorted_classes) < len(model_defs):
        for class_name, model_code in model_defs.items():
            if class_name in sorted_classes:
                continue
            
            dependencies = [dep for dep in all_custom_classes if f"({dep})" in model_code]
            if all(dep in sorted_classes for dep in dependencies):
                sorted_classes.append(class_name)

    import_str = "from pydantic import BaseModel\n"
    other_imports = sorted(list(all_imports - {"BaseModel"}))
    if other_imports:
        import_str += f"from typing import {', '.join(other_imports)}\n"
    
    import_str += "\n\n"

    for class_name in sorted_classes:
        all_models_code += model_defs[class_name]

    with open(output_path, 'w') as f:
        f.write(import_str)
        f.write(all_models_code)

    print(f"Models generated at {output_path}")

if __name__ == "__main__":
    main()
