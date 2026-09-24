#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "expat.h"

typedef struct {
    XML_Parser parser;
    int saw_junk;
} State;

static const char *
type_name(enum XML_Content_Type type)
{
    switch (type) {
        case XML_CTYPE_EMPTY:  return "EMPTY";
        case XML_CTYPE_ANY:    return "ANY";
        case XML_CTYPE_MIXED:  return "MIXED";
        case XML_CTYPE_NAME:   return "NAME";
        case XML_CTYPE_CHOICE: return "CHOICE";
        case XML_CTYPE_SEQ:    return "SEQ";
        default:               return "UNKNOWN";
    }
}

static const char *
quant_name(enum XML_Content_Quant quant)
{
    switch (quant) {
        case XML_CQUANT_NONE: return "NONE";
        case XML_CQUANT_OPT:  return "OPT";
        case XML_CQUANT_REP:  return "REP";
        case XML_CQUANT_PLUS: return "PLUS";
        default:              return "UNKNOWN";
    }
}

static void
print_model(const XML_Content *model)
{
    if (model == NULL) {
        printf("NULL");
        return;
    }

    printf("%s:%s", type_name(model->type), quant_name(model->quant));

    if (model->name != NULL) {
        printf("(%s)", model->name);
    }

    if (model->numchildren > 0 && model->children != NULL) {
        unsigned int i;

        printf("[");
        for (i = 0; i < model->numchildren; i++) {
            if (i != 0) {
                printf(",");
            }
            print_model(&model->children[i]);
        }
        printf("]");
    }
}

static void XMLCALL
element_decl(void *userData, const XML_Char *name, XML_Content *model)
{
    State *state = (State *)userData;

    if (strcmp(name, "junk") == 0) {
        state->saw_junk = 1;

        printf("MODEL=");
        print_model(model);
        printf("\n");
    }

    XML_FreeContentModel(state->parser, model);
}

int
main(int argc, char **argv)
{
    FILE *fp;
    long size;
    char *buffer;
    XML_Parser parser;
    enum XML_Status status;
    State state;

    if (argc != 2) {
        fprintf(stderr, "usage: %s input.xml\n", argv[0]);
        return 64;
    }

    fp = fopen(argv[1], "rb");
    if (!fp) {
        perror("fopen");
        return 65;
    }

    fseek(fp, 0, SEEK_END);
    size = ftell(fp);
    rewind(fp);

    buffer = malloc((size_t)size);
    if (!buffer) {
        fclose(fp);
        return 66;
    }

    if (fread(buffer, 1, (size_t)size, fp) != (size_t)size) {
        free(buffer);
        fclose(fp);
        return 67;
    }

    fclose(fp);

    parser = XML_ParserCreate(NULL);
    if (!parser) {
        free(buffer);
        return 68;
    }

    state.parser = parser;
    state.saw_junk = 0;

    XML_SetUserData(parser, &state);
    XML_SetElementDeclHandler(parser, element_decl);

    status = XML_Parse(parser, buffer, (int)size, XML_TRUE);

    if (status != XML_STATUS_OK) {
        fprintf(
            stderr,
            "PARSE_ERROR code=%d line=%lu column=%lu message=\"%s\"\n",
            XML_GetErrorCode(parser),
            XML_GetCurrentLineNumber(parser),
            XML_GetCurrentColumnNumber(parser),
            XML_ErrorString(XML_GetErrorCode(parser))
        );

        XML_ParserFree(parser);
        free(buffer);
        return 2;
    }

    XML_ParserFree(parser);
    free(buffer);

    if (!state.saw_junk) {
        fprintf(stderr, "MODEL_NOT_OBSERVED\n");
        return 3;
    }

    return 0;
}
