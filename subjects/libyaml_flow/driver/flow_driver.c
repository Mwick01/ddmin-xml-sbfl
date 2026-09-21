#include <stdio.h>
#include <string.h>

#include <yaml.h>

static void
print_hex(
    const unsigned char *data,
    size_t length
)
{
    size_t i;

    if (data == NULL) {
        printf("-");
        return;
    }

    for (i = 0; i < length; i++) {
        printf("%02x", data[i]);
    }
}

static void
print_cstring_hex(
    const unsigned char *data
)
{
    if (data == NULL) {
        printf("-");
        return;
    }

    print_hex(
        data,
        strlen((const char *)data)
    );
}

static void
print_event(
    const yaml_event_t *event
)
{
    switch (event->type) {

    case YAML_STREAM_START_EVENT:
        printf("EV STREAM_START\n");
        break;

    case YAML_STREAM_END_EVENT:
        printf("EV STREAM_END\n");
        break;

    case YAML_DOCUMENT_START_EVENT:
        printf("EV DOCUMENT_START\n");
        break;

    case YAML_DOCUMENT_END_EVENT:
        printf("EV DOCUMENT_END\n");
        break;

    case YAML_ALIAS_EVENT:
        printf("EV ALIAS anchor=");
        print_cstring_hex(
            event->data.alias.anchor
        );
        printf("\n");
        break;

    case YAML_SCALAR_EVENT:
        printf(
            "EV SCALAR len=%zu value=",
            event->data.scalar.length
        );

        print_hex(
            event->data.scalar.value,
            event->data.scalar.length
        );

        printf(" anchor=");
        print_cstring_hex(
            event->data.scalar.anchor
        );

        printf(" tag=");
        print_cstring_hex(
            event->data.scalar.tag
        );

        printf("\n");
        break;

    case YAML_SEQUENCE_START_EVENT:
        printf("EV SEQUENCE_START");
        printf(" anchor=");
        print_cstring_hex(
            event->data.sequence_start.anchor
        );
        printf(" tag=");
        print_cstring_hex(
            event->data.sequence_start.tag
        );
        printf("\n");
        break;

    case YAML_SEQUENCE_END_EVENT:
        printf("EV SEQUENCE_END\n");
        break;

    case YAML_MAPPING_START_EVENT:
        printf("EV MAPPING_START");
        printf(" anchor=");
        print_cstring_hex(
            event->data.mapping_start.anchor
        );
        printf(" tag=");
        print_cstring_hex(
            event->data.mapping_start.tag
        );
        printf("\n");
        break;

    case YAML_MAPPING_END_EVENT:
        printf("EV MAPPING_END\n");
        break;

    case YAML_NO_EVENT:
    default:
        printf(
            "EV UNKNOWN type=%d\n",
            (int)event->type
        );
        break;
    }
}

int
main(
    int argc,
    char **argv
)
{
    FILE *input;
    yaml_parser_t parser;
    yaml_event_t event;
    int stream_end = 0;

    if (argc != 2) {
        fprintf(
            stderr,
            "usage: %s INPUT.yaml\n",
            argv[0]
        );
        return 2;
    }

    input = fopen(
        argv[1],
        "rb"
    );

    if (input == NULL) {
        perror("fopen");
        return 2;
    }

    if (!yaml_parser_initialize(&parser)) {
        fprintf(
            stderr,
            "yaml_parser_initialize failed\n"
        );

        fclose(input);
        return 2;
    }

    yaml_parser_set_input_file(
        &parser,
        input
    );

    while (!stream_end) {

        if (!yaml_parser_parse(
                &parser,
                &event
            )) {

            fprintf(
                stderr,
                "parse_error=%d problem=%s "
                "line=%zu column=%zu\n",
                (int)parser.error,
                parser.problem != NULL
                    ? parser.problem
                    : "(none)",
                parser.problem_mark.line + 1,
                parser.problem_mark.column + 1
            );

            yaml_parser_delete(
                &parser
            );

            fclose(input);

            return 1;
        }

        print_event(&event);

        if (
            event.type ==
            YAML_STREAM_END_EVENT
        ) {
            stream_end = 1;
        }

        yaml_event_delete(
            &event
        );
    }

    yaml_parser_delete(
        &parser
    );

    fclose(input);

    return 0;
}
