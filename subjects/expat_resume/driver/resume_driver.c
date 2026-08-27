#include <expat.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void end_element(
    void *user_data,
    const char *name
) {
    XML_Parser parser = (XML_Parser)user_data;

    if (strcmp(name, "doc") == 0) {
        XML_StopParser(
            parser,
            XML_TRUE
        );
    }
}


static char *read_file(
    const char *path,
    size_t *size_out
) {
    FILE *file = fopen(path, "rb");

    if (!file) {
        return NULL;
    }

    if (fseek(file, 0, SEEK_END) != 0) {
        fclose(file);
        return NULL;
    }

    long length = ftell(file);

    if (length < 0) {
        fclose(file);
        return NULL;
    }

    rewind(file);

    char *buffer = malloc(
        (size_t)length + 1
    );

    if (!buffer) {
        fclose(file);
        return NULL;
    }

    size_t read_count = fread(
        buffer,
        1,
        (size_t)length,
        file
    );

    fclose(file);

    if (
        read_count
        != (size_t)length
    ) {
        free(buffer);
        return NULL;
    }

    buffer[length] = '\0';

    *size_out = (size_t)length;

    return buffer;
}


int main(
    int argc,
    char **argv
) {
    if (argc != 2) {
        fprintf(
            stderr,
            "usage: %s input.xml\n",
            argv[0]
        );

        return 2;
    }

    size_t input_size = 0;

    char *input = read_file(
        argv[1],
        &input_size
    );

    if (!input) {
        fprintf(
            stderr,
            "READ_ERROR\n"
        );

        return 2;
    }

    XML_Parser parser = (
        XML_ParserCreate(NULL)
    );

    if (!parser) {
        free(input);
        return 2;
    }

    XML_SetElementHandler(
        parser,
        NULL,
        end_element
    );

    XML_SetUserData(
        parser,
        parser
    );

    enum XML_Status result = XML_Parse(
        parser,
        input,
        (int)input_size,
        XML_TRUE
    );

    while (
        result
        == XML_STATUS_SUSPENDED
    ) {
        result = XML_ResumeParser(
            parser
        );
    }

    if (
        result
        == XML_STATUS_OK
    ) {
        printf("STATUS=OK\n");
    } else {
        printf(
            "STATUS=ERROR:%s\n",
            XML_ErrorString(
                XML_GetErrorCode(
                    parser
                )
            )
        );
    }

    XML_ParserFree(parser);
    free(input);

    return 0;
}